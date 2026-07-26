"""MIO Core · Tool Orchestrator — gerçek yürütme motoru (ADR-0002 Madde 8), LLM-BAĞIMSIZ çekirdek.

Pasif bir istek-ileten değil; şunları yapar: Capability Selection · Permission/Approval Check ·
Cost/Risk Evaluation · Executive Governance (E4) · Retry/Fallback · Result Validation · Execution
Monitoring · Audit Logging. **Hiçbir Brain doğrudan API kullanmaz** — her dış erişim buradan.

Çekirdek DETERMİNİSTİKtir; GERÇEK yürütme (native/MCP/LLM) enjekte edilen `ToolExecutor` adaptörlerine
devredilir. Bir yetenek için executor yoksa DÜRÜST başarısızlık döner (mock/placeholder yok). LLM buraya
yalnız bir ToolExecutor'dur (X4 Model Gateway) — karar verici değil.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from mio_core.capability import Capability, CapabilityRegistry, RiskLevel
from mio_core.executive.governance import (
    DecisionRequest,
    EXTERNAL,
    GovernanceEngine,
    IRREVERSIBLE,
    REVERSIBLE,
    Verdict,
)
from mio_core.executive.models import new_id, now_iso
from mio_core.platform.resilience import CircuitBreaker, CircuitState, ResiliencePolicy

logger = __import__("logging").getLogger("mio.execution.orchestrator")

__all__ = [
    "ToolRequest",
    "ToolResult",
    "ToolExecutor",
    "AuditEntry",
    "ToolAuditStore",
    "SQLiteToolAuditStore",
    "ToolOrchestrator",
]


@dataclass
class ToolRequest:
    capability: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    requester: str = "executive"                  # Brain adı ya da "executive"
    reversibility: str = REVERSIBLE               # reversible | irreversible | external
    goal_id: Optional[str] = None
    context_ref: str = ""
    user_approved: bool = False                   # kullanıcı açık onayı (Financial Rule kapısı)
    max_retries: Optional[int] = None             # None → orchestrator varsayılanı


@dataclass
class ToolResult:
    success: bool
    capability: str
    action: str
    output: Any = None
    error: str = ""
    blocked: bool = False                         # izin/onay/governance ile engellendi
    reason: str = ""
    verdict: Optional[str] = None                 # governance/approval vardası
    attempts: int = 0
    fallback_used: Optional[str] = None
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "capability": self.capability, "action": self.action,
                "output": self.output, "error": self.error, "blocked": self.blocked,
                "reason": self.reason, "verdict": self.verdict, "attempts": self.attempts,
                "fallback_used": self.fallback_used, "latency_ms": self.latency_ms}


class ToolExecutor(Protocol):
    """GERÇEK yürütme adaptörü (native/MCP/LLM). Başarıda çıktı döner, başarısızlıkta EXCEPTION fırlatır."""
    def execute(self, capability: Capability, action: str, args: dict[str, Any]) -> Any: ...


# --------------------------------------------------------------------------- #
# Audit (her araç kullanımı kaydedilir — ADR-0002 Madde 8)
# --------------------------------------------------------------------------- #
@dataclass
class AuditEntry:
    requester: str
    capability: str
    action: str
    success: bool
    blocked: bool
    verdict: Optional[str]
    error: str
    latency_ms: int
    id: str = field(default_factory=new_id)
    at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "requester": self.requester, "capability": self.capability,
                "action": self.action, "success": self.success, "blocked": self.blocked,
                "verdict": self.verdict, "error": self.error, "latency_ms": self.latency_ms, "at": self.at}


class ToolAuditStore(Protocol):
    def append(self, entry: AuditEntry) -> None: ...
    def list(self, limit: int = 100) -> list[AuditEntry]: ...
    def close(self) -> None: ...


class SQLiteToolAuditStore:
    def __init__(self, path: str = "mio_tool_audit.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.execute("CREATE TABLE IF NOT EXISTS tool_audit (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
            self._conn.commit()

    def append(self, entry: AuditEntry) -> None:
        with self._lock:
            self._conn.execute("INSERT INTO tool_audit (id, data) VALUES (?, ?)",
                               (entry.id, json.dumps(entry.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def list(self, limit: int = 100) -> list[AuditEntry]:
        rows = self._conn.execute(
            "SELECT data FROM tool_audit ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = json.loads(r["data"])
            out.append(AuditEntry(requester=d["requester"], capability=d["capability"], action=d["action"],
                                  success=d["success"], blocked=d["blocked"], verdict=d.get("verdict"),
                                  error=d.get("error", ""), latency_ms=d.get("latency_ms", 0),
                                  id=d["id"], at=d["at"]))
        return out

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class ToolOrchestrator:
    """Gerçek yürütme motoru. Capability Registry + (opsiyonel) E4 Governance + audit ile çalışır."""

    def __init__(self, capabilities: CapabilityRegistry, *, governance: Optional[GovernanceEngine] = None,
                 audit_store: Optional[ToolAuditStore] = None, default_retries: int = 1,
                 resilience: Optional[ResiliencePolicy] = None) -> None:
        self._caps = capabilities
        self._gov = governance
        self._audit = audit_store
        self._default_retries = max(0, default_retries)
        self._executors: dict[str, ToolExecutor] = {}
        self._on_result = None                       # (request, result) → None; Meta MCP metrik dinleyicisi
        # Madde 28 (Resilience): opt-in policy. None → tarihsel davranış (backward-compat). Set → circuit
        # breaker + exponential backoff + retry (yalnız yürütücü çağrısı katmanında).
        self._resilience = resilience
        self._breakers: dict[str, CircuitBreaker] = {}

    def circuit_state(self, capability: str) -> str:
        """Bir yeteneğin devre durumu (closed/open/half_open) — gözlemlenebilirlik (Madde 27)."""
        br = self._breakers.get(capability)
        return br.state if br is not None else CircuitState.CLOSED

    def set_result_listener(self, listener) -> None:
        """Her yürütme sonucunu dinler (Meta MCP: health/trust/benchmark gerçek kullanımdan)."""
        self._on_result = listener

    def register_executor(self, capability_name: str, executor: ToolExecutor) -> None:
        """Bir yeteneğin GERÇEK yürütücüsünü bağlar (native/MCP/LLM). Ayrıca yeteneği 'connected' yapar."""
        self._executors[capability_name] = executor
        self._caps.set_connected(capability_name, True)

    def execute(self, request: ToolRequest) -> ToolResult:
        t0 = time.time()
        res = self._run(request)
        res.latency_ms = int((time.time() - t0) * 1000)
        if self._audit is not None:
            self._audit.append(AuditEntry(
                requester=request.requester, capability=request.capability, action=request.action,
                success=res.success, blocked=res.blocked, verdict=res.verdict, error=res.error,
                latency_ms=res.latency_ms))
        if self._on_result is not None:
            try:
                self._on_result(request, res)         # Meta MCP: health/trust/benchmark
            except Exception as exc:  # noqa: BLE001 — dinleyici hatası yürütmeyi bozmaz AMA sessiz değil (Madde 27)
                logger.warning("Orchestrator sonuç-dinleyici hatası (%s:%s): %s",
                               request.capability, request.action, exc)
        return res

    # -- iç akış ------------------------------------------------------------ #
    def _run(self, req: ToolRequest) -> ToolResult:
        cap = self._caps.get(req.capability)
        if cap is None:
            return self._block(req, "Bilinmeyen yetenek (kayıtlı değil).")
        if not cap.usable_by(req.requester):
            return self._block(req, f"'{req.requester}' bu yeteneği kullanamaz (usable_by).")
        if not cap.connected:
            return self._block(req, "Yetenek bağlı değil (bu ortamda erişim yok).")

        # Kullanıcı-onay kapısı (Financial Rule): onay gerekliyse ve verilmemişse yürütme YOK.
        if cap.requires_user_approval and not req.user_approved:
            return self._block(req, "Kullanıcı açık onayı gerekiyor (Financial Rule).",
                               verdict=Verdict.AWAIT_APPROVAL.value)

        # Executive Governance (E4): yüksek risk / geri-alınamaz / dış → Executive kararı.
        if self._gov is not None and self._needs_governance(cap, req):
            gv = self._gov.decide(DecisionRequest(
                kind="tool_use", chosen=f"{cap.name}:{req.action}", goal_id=req.goal_id,
                reversibility=req.reversibility, required_capabilities=[cap.name],
                context_ref=req.context_ref, evidence_refs=[f"tool:{cap.name}"],
                source=req.requester))
            if gv.verdict is not Verdict.APPROVE:
                return self._block(req, f"Governance izin vermedi ({gv.verdict.value}).",
                                   verdict=gv.verdict.value)

        # Yürütme (retry) + fallback
        result = self._execute_capability(cap, req)
        if result.success or result.blocked:
            return result
        for alt_name in cap.alternatives:
            alt = self._caps.get(alt_name)
            if alt and alt.connected and alt.usable_by(req.requester) and alt_name in self._executors:
                fb = self._execute_capability(alt, req)
                if fb.success:
                    fb.fallback_used = alt_name
                    fb.attempts += result.attempts
                    return fb
        return result

    def _execute_capability(self, cap: Capability, req: ToolRequest) -> ToolResult:
        executor = self._executors.get(cap.name)
        if executor is None:
            return self._block(req, f"'{cap.name}' için bağlı yürütücü yok.")
        pol = self._resilience
        # Circuit breaker (Madde 28): açıksa bağımlılığı hammer etme → zarif düşüş (graceful degradation).
        breaker = None
        if pol is not None:
            breaker = self._breakers.setdefault(cap.name, pol.new_breaker())
            if not breaker.allow():
                logger.warning("Orchestrator: '%s' devresi AÇIK — çağrı korundu", cap.name)
                return ToolResult(success=False, capability=cap.name, action=req.action,
                                  error="circuit_open", reason="Devre açık (circuit breaker) — bağımlılık korunuyor")
        retries = req.max_retries if req.max_retries is not None else self._default_retries
        attempts, last_err = 0, ""
        for i in range(retries + 1):
            attempts += 1
            try:
                output = executor.execute(cap, req.action, req.args)
                if breaker is not None:
                    breaker.on_success()
                return ToolResult(success=True, capability=cap.name, action=req.action,
                                  output=output, attempts=attempts)
            except Exception as e:  # noqa: BLE001 — yürütme sınırı; hata sonuca dönüşür
                last_err = str(e)[:300]
                if pol is not None and i < retries:      # Exponential backoff (yalnız policy varsa)
                    delay = pol.backoff.delay(attempts)
                    if delay > 0:
                        pol.sleeper(delay)
        if breaker is not None:
            breaker.on_failure()
        return ToolResult(success=False, capability=cap.name, action=req.action,
                          error=last_err, attempts=attempts)

    @staticmethod
    def _needs_governance(cap: Capability, req: ToolRequest) -> bool:
        return cap.risk_level == RiskLevel.HIGH or req.reversibility in (IRREVERSIBLE, EXTERNAL)

    @staticmethod
    def _block(req: ToolRequest, reason: str, verdict: Optional[str] = None) -> ToolResult:
        return ToolResult(success=False, capability=req.capability, action=req.action,
                          blocked=True, reason=reason, verdict=verdict)
