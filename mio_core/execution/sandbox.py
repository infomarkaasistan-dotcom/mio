"""MIO Core · MCP Sandbox (Öncelik 2) — yeni MCP izole yaşam-döngüsü, LLM-BAĞIMSIZ.

Hiçbir yeni MCP doğrudan production'a girmez. Önce İZOLE bir registry/orchestrator'da yaşam-döngüsünden
geçer: identity → manifest → permission → dependency → security → policy → stress → benchmark → capability
extraction → Executive review. Verdict: approved | needs_approval | rejected. Yalnız reddedilmeyen MCP
production'a (gerçek CapabilityDiscovery) promote edilir.

Bazı aşamalar (dependency/security) DÜRÜST 'advisory'dir — gerçek tarama araçları olmadan 'güvenli'
demez, 'kırmızı bayrak yok' der. Deterministik; LLM çağırmaz."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from mio_core.capability import CapabilityRegistry, RiskLevel
from mio_core.events import Ev
from mio_core.execution.mcp_hub import MCPClient, MCPHub, ServerStatus
from mio_core.execution.meta_mcp import CapabilityPolicyEngine
from mio_core.execution.orchestrator import ToolOrchestrator, ToolRequest

__all__ = ["StageResult", "SandboxReport", "SandboxPipeline"]


@dataclass
class StageResult:
    stage: str
    passed: bool
    note: str = ""
    severity: str = "info"                       # info | warn | advisory

    def to_dict(self):
        return {"stage": self.stage, "passed": self.passed, "note": self.note, "severity": self.severity}


@dataclass
class SandboxReport:
    servers: list[str]
    stages: list[StageResult] = field(default_factory=list)
    verdict: str = "rejected"                    # approved | needs_approval | rejected
    capabilities: int = 0
    needs_approval: list[str] = field(default_factory=list)

    def to_dict(self):
        return {"servers": self.servers, "verdict": self.verdict, "capabilities": self.capabilities,
                "needs_approval": self.needs_approval, "stages": [s.to_dict() for s in self.stages]}


class SandboxPipeline:
    def __init__(self, *, policy: Optional[CapabilityPolicyEngine] = None, bus=None) -> None:
        self._policy = policy or CapabilityPolicyEngine()
        self._bus = bus

    def evaluate(self, client: MCPClient) -> SandboxReport:
        reg = CapabilityRegistry()                # İZOLE — production'a dokunmaz
        orch = ToolOrchestrator(reg)
        hub = MCPHub(client)
        hub.discover()
        hub.health_check()
        servers = hub.list_servers()
        healthy = [s for s in servers if s.status == ServerStatus.HEALTHY]
        stages: list[StageResult] = []

        def _stage(name, passed, note, severity="info"):
            r = StageResult(name, passed, note, severity)
            stages.append(r)
            if self._bus:
                self._bus.publish(Ev.SANDBOX_STAGE, {"stage": name, "passed": passed, "note": note})

        _stage("identity_verification", bool(servers), f"{len(servers)} sunucu, {len(healthy)} sağlıklı")
        _stage("manifest_validation", bool(healthy) and all(s.tools for s in healthy),
               f"{sum(len(s.tools) for s in healthy)} araç")
        perms = sorted({p for s in healthy for t in s.tools for p in t.required_permissions})
        _stage("permission_scan", True, f"izinler: {', '.join(perms) or 'yok'}")
        _stage("dependency_scan", True, "advisory: gerçek bağımlılık taraması yapılmadı", "advisory")
        risky = [t.name for s in healthy for t in s.tools if t.risk_level == RiskLevel.HIGH]
        _stage("security_scan", True, f"advisory: {len(risky)} yüksek-riskli araç", "warn" if risky else "info")

        bound = hub.map_and_bind(reg, orch)
        needs_approval = [c.name for c in reg.list() if c.requires_user_approval]
        _stage("policy_validation", True, f"onay bekleyen: {len(needs_approval)}")

        probe = next((c for c in reg.list() if c.risk_level == RiskLevel.LOW), None)
        if probe is not None:
            res = orch.execute(ToolRequest(probe.name, "probe", {}))
            _stage("stress_test", res.success or res.blocked,
                   f"probe {probe.name}: {'ok' if res.success else (res.reason or res.error)}")
            _stage("performance_benchmark", True, f"{res.latency_ms}ms")
        else:
            _stage("stress_test", True, "düşük-riskli probe aracı yok", "info")
            _stage("performance_benchmark", True, "atlandı", "info")

        _stage("capability_extraction", bound > 0, f"{bound} capability çıkarıldı")

        hard_fail = any((not s.passed) and s.severity != "advisory" for s in stages)
        if not healthy or hard_fail:
            verdict = "rejected"
        elif needs_approval:
            verdict = "needs_approval"            # Executive/kullanıcı onayı — capability'ler zaten gated
        else:
            verdict = "approved"

        report = SandboxReport(servers=[s.name for s in servers], stages=stages, verdict=verdict,
                               capabilities=bound, needs_approval=needs_approval)
        if self._bus:
            self._bus.publish(Ev.SANDBOX_RESULT, report.to_dict())
        return report

    def promote(self, client: MCPClient, discovery) -> Optional[object]:
        """Sandbox'tan geçir; reddedilmezse GERÇEK production discovery'sine promote et (onay-gated caps
        çağrı anında kapılı kalır). Reddedilirse None (production'a girmez)."""
        report = self.evaluate(client)
        if report.verdict == "rejected":
            return None
        return discovery.discover(client)
