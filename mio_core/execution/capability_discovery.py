"""MIO Core · Capability Discovery — MCP ekosistemini YÖNETEN pipeline (Meta MCP), LLM-BAĞIMSIZ.

Kullanıcının çizdiği akış: Yeni MCP → Manifest okundu → Risk analizi → Capability çıkarıldı → Registry/
Executive güncellendi → (gerekirse) kullanıcı izni → Brain'ler yeni yeteneği kullanır. Hepsi HİÇ KOD
YAZMADAN: MCP protokolü evrensel adaptördür; MIO herhangi bir MCP'yi otomatik keşfedip Capability sistemine
ekler.

`CapabilityDiscovery.discover(client)` bu pipeline'ı çalıştırır (çalışma anında da). `capability_index()`
Meta katalogdur: "ne yapabilirim / risk / güven / izin / nereden geldi". Bu, MIO'yu "MCP kullanan sistem"
değil "MCP ekosistemini yöneten işletim sistemi" yapar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from mio_core.capability import CapabilityRegistry
from mio_core.execution.mcp_hub import MCPClient, MCPHub, ServerStatus
from mio_core.execution.orchestrator import ToolOrchestrator

__all__ = ["DiscoveredCapability", "DiscoveryReport", "CapabilityDiscovery", "capability_index"]


@dataclass
class DiscoveredCapability:
    name: str
    provenance: str
    risk: str
    requires_approval: bool
    connected: bool
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "provenance": self.provenance, "risk": self.risk,
                "requires_approval": self.requires_approval, "connected": self.connected,
                "has_manifest": bool(self.parameters)}


@dataclass
class DiscoveryReport:
    servers_discovered: int
    healthy_servers: int
    capabilities: list[DiscoveredCapability] = field(default_factory=list)
    needs_approval: list[str] = field(default_factory=list)
    executive_decision_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"servers_discovered": self.servers_discovered, "healthy_servers": self.healthy_servers,
                "capabilities": [c.to_dict() for c in self.capabilities],
                "needs_approval": list(self.needs_approval),
                "executive_decision_id": self.executive_decision_id}


class CapabilityDiscovery:
    """MCP keşif pipeline'ı. Herhangi bir MCP'yi (300 farklı olsa da) sıfır kodla capability'ye çevirir,
    Executive'e raporlar ve risk-kapılı izinle Brain'lerin kullanımına açar."""

    def __init__(self, capabilities: CapabilityRegistry, orchestrator: ToolOrchestrator, *,
                 state=None, on_report: Optional[Callable[[DiscoveryReport], None]] = None) -> None:
        self._caps = capabilities
        self._orch = orchestrator
        self._state = state                             # E1 ExecutiveState (opsiyonel) — rapor için
        self._on_report = on_report

    def discover(self, client: MCPClient) -> DiscoveryReport:
        """Pipeline: discover → health → manifest+risk → capability çıkar+bind → Executive'e rapor → izin bayrağı."""
        hub = MCPHub(client)
        n_servers = hub.discover()
        hub.health_check()

        collected: list[DiscoveredCapability] = []

        def _on_cap(server, cap) -> None:
            collected.append(DiscoveredCapability(
                name=cap.name, provenance=cap.provenance, risk=cap.risk_level,
                requires_approval=cap.requires_user_approval, connected=cap.connected,
                parameters=cap.parameters))

        hub.map_and_bind(self._caps, self._orch, on_capability=_on_cap)

        needs_approval = [c.name for c in collected if c.requires_approval]
        healthy = sum(1 for s in hub.list_servers() if s.status == ServerStatus.HEALTHY)
        report = DiscoveryReport(servers_discovered=n_servers, healthy_servers=healthy,
                                 capabilities=collected, needs_approval=needs_approval)

        # Executive'e rapor (E1 karar defterine): "yeni yetenekler keşfedildi" — iç-gözlenebilir kayıt.
        if self._state is not None and collected:
            d = self._state.record_decision(
                kind="capability_discovery",
                chosen=f"{len(collected)} yeni yetenek keşfedildi ({healthy} sağlıklı sunucu)",
                rationale=("MCP keşfi: " + ", ".join(c.name for c in collected)
                           + (f" | onay bekleyen: {', '.join(needs_approval)}" if needs_approval else "")),
                evidence_refs=sorted({f"mcp:{c.provenance}" for c in collected}),
                expectation="Yeni yetenekler Executive kontrolü + Tool Orchestrator üzerinden kullanılabilir.")
            report.executive_decision_id = d.id

        if self._on_report is not None:
            self._on_report(report)
        return report


def capability_index(capabilities: CapabilityRegistry) -> list[dict[str, Any]]:
    """Meta MCP kataloğu: MIO'nun TÜM yeteneklerinin özeti (ne / kaynak / risk / bağlı / izin / kim kullanır /
    nereden). 'Şu an neleri yapabilirim, hangi riskle, hangi izinle?' sorusunun tam cevabı."""
    return sorted(
        [{"name": c.name, "source": c.source, "provenance": c.provenance, "risk": c.risk_level,
          "connected": c.connected, "requires_approval": c.requires_user_approval,
          "usable_by": list(c.usable_by_brains), "incurs_cost": c.incurs_cost}
         for c in capabilities.list()],
        key=lambda d: (not d["connected"], d["name"]))
