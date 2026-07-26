"""MIO Core · Meta MCP Manager (v2.0) — MCP ekosistemini YÖNETEN üst katman, LLM-BAĞIMSIZ.

MCP Hub yalnız bağlantı/keşif katmanıdır; Meta MCP Manager tüm YAŞAM DÖNGÜSÜNÜ yönetir:
  - Health Monitor: gerçek çağrılardan sağlık (availability/latency/error_rate).
  - Trust Engine: dinamik güven puanı [0-100] (kaynak + risk + gerçek başarı geçmişi).
  - Capability Graph: yetenekleri kategoriye göre gruplar (alternatifler).
  - Load Balancer + Cost Optimizer: aynı kategoride en iyi alternatifi seçer (önce ücretsiz/yerel — Purpose).
  - Policy Engine: merkezi kurallar (delete→Executive, financial→User, deploy→her ikisi).
  - Capability Memory: ilk keşif/kullanım, son kullanım, başarı oranı.
  - Rich Catalog: her yeteneğin tam öz-modeli (statik + dinamik).

Metrikler GERÇEK kullanımdan gelir (Tool Orchestrator `set_result_listener` ile bağlanır). Deterministik;
LLM hiçbir aşamada zorunlu değildir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from mio_core.capability import Capability, CapabilityRegistry, MaturityLevel, RiskLevel
from mio_core.executive.models import now_iso

__all__ = ["CapabilityMetrics", "CapabilityPolicyEngine", "MetaMCPManager"]

_TRUST_BASE = {"native": 85, "tool": 80, "mcp": 60}
_DESTRUCTIVE = ("delete", "remove", "drop", "kill", "deploy", "push")


@dataclass
class CapabilityMetrics:
    first_seen: str = field(default_factory=now_iso)
    calls: int = 0
    successes: int = 0
    errors: int = 0
    timeouts: int = 0
    total_latency_ms: int = 0
    first_used: Optional[str] = None
    last_used: Optional[str] = None

    @property
    def success_rate(self) -> Optional[float]:
        used = self.successes + self.errors
        return round(self.successes / used, 3) if used else None

    @property
    def error_rate(self) -> Optional[float]:
        used = self.successes + self.errors
        return round(self.errors / used, 3) if used else None

    @property
    def avg_latency_ms(self) -> Optional[int]:
        return int(self.total_latency_ms / self.calls) if self.calls else None

    def to_dict(self) -> dict[str, Any]:
        return {"first_seen": self.first_seen, "calls": self.calls, "successes": self.successes,
                "errors": self.errors, "timeouts": self.timeouts, "total_latency_ms": self.total_latency_ms,
                "success_rate": self.success_rate, "error_rate": self.error_rate,
                "avg_latency_ms": self.avg_latency_ms, "first_used": self.first_used,
                "last_used": self.last_used}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CapabilityMetrics":
        m = cls(first_seen=d.get("first_seen") or now_iso())
        m.calls = int(d.get("calls", 0)); m.successes = int(d.get("successes", 0))
        m.errors = int(d.get("errors", 0)); m.timeouts = int(d.get("timeouts", 0))
        m.total_latency_ms = int(d.get("total_latency_ms", 0))
        m.first_used, m.last_used = d.get("first_used"), d.get("last_used")
        return m


class CapabilityPolicyEngine:
    """Merkezi Capability Policy: bir yetenek için gereken onaylar (Executive / User). Deterministik kurallar."""

    def required_approvals(self, cap: Capability) -> list[str]:
        req: list[str] = []
        destructive = any(t in cap.name.lower() for t in _DESTRUCTIVE)
        if cap.risk_level == RiskLevel.HIGH or destructive:
            req.append("executive")
        if cap.incurs_cost or cap.requires_user_approval or cap.category == "payment":
            req.append("user")
        if "deploy" in cap.name.lower():                     # deploy → Executive + User
            req = ["executive", "user"]
        return req

    def evaluate(self, cap: Capability, *, user_approved: bool = False,
                 executive_approved: bool = False) -> tuple[bool, str, list[str]]:
        req = self.required_approvals(cap)
        missing = []
        if "user" in req and not user_approved:
            missing.append("user")
        if "executive" in req and not executive_approved:
            missing.append("executive")
        if missing:
            return False, f"Onay eksik: {', '.join(missing)}", req
        return True, "izinli", req


class MetaMCPManager:
    """MCP ekosistemi yöneticisi. Gerçek kullanımdan health/trust/benchmark; graph/load-balance/cost/policy."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self._caps = capabilities
        self._metrics: dict[str, CapabilityMetrics] = {}
        self.policy = CapabilityPolicyEngine()

    # -- Health Monitor (gerçek kullanımdan) ------------------------------- #
    def attach(self, orchestrator) -> None:
        """Tool Orchestrator'ı dinler → her çağrı health/trust/benchmark'ı besler."""
        orchestrator.set_result_listener(self._on_result)

    def _on_result(self, request, result) -> None:
        self.record(request.capability, success=result.success, blocked=result.blocked,
                    latency_ms=result.latency_ms)

    def record(self, capability: str, *, success: bool, latency_ms: int = 0,
               blocked: bool = False, timeout: bool = False) -> None:
        m = self._metric(capability)
        m.calls += 1
        m.total_latency_ms += max(0, latency_ms)
        if timeout:
            m.timeouts += 1
        if blocked:
            return                                           # engel = governance kararı, yeteneğin hatası değil
        if success:
            m.successes += 1
            if m.first_used is None:
                m.first_used = now_iso()
            m.last_used = now_iso()
        else:
            m.errors += 1

    def _metric(self, capability: str) -> CapabilityMetrics:
        return self._metrics.setdefault(capability, CapabilityMetrics())

    def metrics(self, capability: str) -> CapabilityMetrics:
        return self._metric(capability)

    def export_metrics(self) -> dict:
        return {name: m.to_dict() for name, m in self._metrics.items()}

    def import_metrics(self, data: dict) -> int:
        for name, d in (data or {}).items():
            self._metrics[name] = CapabilityMetrics.from_dict(d)
        return len(data or {})

    # -- Trust Engine (dinamik) -------------------------------------------- #
    def trust_score(self, capability: str) -> int:
        cap = self._caps.get(capability)
        if cap is None:
            return 0
        base = _TRUST_BASE.get(cap.source, 55)
        if cap.risk_level == RiskLevel.HIGH:
            base -= 10
        m = self._metrics.get(capability)
        if m and (m.successes + m.errors) >= 3 and m.success_rate is not None:
            base += int((m.success_rate - 0.9) * 40)         # iyi geçmiş → yükselt, kötü → düşür
        return max(0, min(100, base))

    # -- Health state ------------------------------------------------------ #
    def health_state(self, capability: str) -> str:
        m = self._metrics.get(capability)
        if m is None or m.calls == 0:
            cap = self._caps.get(capability)
            return "healthy" if (cap and cap.connected) else "unknown"
        er = m.error_rate or 0.0
        if er > 0.5:
            return "down"
        if er > 0.2:
            return "degraded"
        return "healthy"

    # -- Capability Graph (alternatifler) ---------------------------------- #
    def by_category(self, *, only_connected: bool = True) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {}
        for c in self._caps.list():
            if only_connected and not c.connected:
                continue
            graph.setdefault(c.category, []).append(c.name)
        return graph

    # -- Load Balancer + Cost Optimizer ------------------------------------ #
    def select_best(self, category: str, *, requester: Optional[str] = None) -> Optional[str]:
        """Aynı kategorideki en iyi alternatifi seç: önce ücretsiz/yerel (Purpose), sonra trust×health,
        sonra düşük gecikme. Load balancing + cost optimization birlikte."""
        cands = [c for c in self._caps.list()
                 if c.category == category and c.connected
                 and c.maturity in MaturityLevel.USABLE         # Governance §7: deprecated/retired seçilmez
                 and (requester is None or c.usable_by(requester))]
        if not cands:
            return None

        _hs = {"healthy": 1.0, "unknown": 0.8, "degraded": 0.5, "down": 0.2}

        def _key(c: Capability):
            ts = self.trust_score(c.name)
            hs = _hs.get(self.health_state(c.name), 0.5)
            mat = MaturityLevel.ORDER.get(c.maturity, 3)
            lat = self._metric(c.name).avg_latency_ms or 10_000
            # düşük tuple = daha iyi: önce ücretsiz, sonra olgun+güvenilir+sağlıklı, sonra hızlı
            return (1 if c.incurs_cost else 0, -mat, -(ts * hs), lat)

        cands.sort(key=_key)
        return cands[0].name

    # -- Rich Catalog (zengin öz-model) ------------------------------------ #
    def catalog(self) -> list[dict[str, Any]]:
        out = []
        for c in self._caps.list():
            m = self._metrics.get(c.name)
            out.append({
                "name": c.name, "category": c.category, "source": c.source, "provenance": c.provenance,
                "risk": c.risk_level, "maturity": c.maturity, "connected": c.connected,
                "usable_by": list(c.usable_by_brains),
                "incurs_cost": c.incurs_cost, "requires_approval": c.requires_user_approval,
                "required_approvals": self.policy.required_approvals(c),
                "trust_score": self.trust_score(c.name), "health_state": self.health_state(c.name),
                "metrics": m.to_dict() if m else CapabilityMetrics(first_seen="").to_dict(),
            })
        return sorted(out, key=lambda d: (not d["connected"], -d["trust_score"], d["name"]))
