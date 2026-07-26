"""MIO Core · MCP Hub — dış-dünya yetenek keşif motoru (ADR-0002 Madde 7), çekirdek LLM-BAĞIMSIZ.

MCP Hub sadece bir bağlantı noktası değildir; şu katmanları içerir: Discovery · Registration · Health Check ·
Versioning · Permission/Trust · Capability Mapping · Sandbox · Monitoring · (Audit orchestrator'dan gelir).
Keşfettiği her MCP aracını bir MIO **Capability**'sine haritalar ve Tool Orchestrator'a bir **executor**
olarak bağlar → ilk açılışta MIO'nun "neleri yapabilirim" öz-modeli GERÇEKTEN dolar.

Çekirdek DETERMİNİSTİKtir; gerçek MCP protokol iletişimi enjekte `MCPClient` adaptörüne devredilir (ağ →
deterministik kapsam dışı). İstemci yoksa hiçbir şey keşfedilmez (dürüst). Yalnız SAĞLIKLI sunucuların
araçları bağlanır; sağlıksız/bilinmeyen sunucunun araçları bağlanmaz (dürüst — sahte yetenek yok).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from mio_core.capability import Capability, CapabilityRegistry, RiskLevel, infer_category
from mio_core.execution.orchestrator import ToolOrchestrator
from mio_core.executive.models import new_id, now_iso

__all__ = ["ServerStatus", "TrustLevel", "MCPTool", "MCPServer", "MCPClient", "MCPHub"]


class ServerStatus:
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class TrustLevel:
    UNTRUSTED = "untrusted"
    TRUSTED = "trusted"
    VERIFIED = "verified"


@dataclass
class MCPTool:
    name: str
    description: str = ""
    risk_level: str = RiskLevel.MEDIUM
    required_permissions: list[str] = field(default_factory=list)
    usable_by_brains: list[str] = field(default_factory=lambda: ["*"])
    incurs_cost: bool = False
    requires_user_approval: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)     # MCP manifest (JSON Schema) → nasıl çağrılır


@dataclass
class MCPServer:
    name: str
    url: str = ""
    version: str = ""
    transport: str = "stdio"                       # stdio | http | sse
    trust_level: str = TrustLevel.UNTRUSTED
    sandboxed: bool = True
    status: str = ServerStatus.UNKNOWN
    tools: list[MCPTool] = field(default_factory=list)
    id: str = field(default_factory=new_id)
    last_health_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "url": self.url, "version": self.version,
                "transport": self.transport, "trust_level": self.trust_level, "sandboxed": self.sandboxed,
                "status": self.status, "tools": [t.name for t in self.tools],
                "last_health_at": self.last_health_at}


class MCPClient(Protocol):
    """GERÇEK MCP transport adaptörü (ağ/stdio). Çekirdek bunu enjekte alır; kendisi ağ yapmaz."""
    def discover(self) -> list[MCPServer]: ...
    def list_tools(self, server: MCPServer) -> list[MCPTool]: ...
    def health(self, server: MCPServer) -> str: ...
    def call(self, server: MCPServer, tool_name: str, args: dict[str, Any]) -> Any: ...


class _MCPExecutor:
    """Bir MCP aracını Tool Orchestrator'a bağlayan ToolExecutor. Gerçek çağrıyı MCPClient'a devreder."""

    def __init__(self, client: MCPClient, server: MCPServer, tool_name: str) -> None:
        self._client = client
        self._server = server
        self._tool = tool_name

    def execute(self, capability: Capability, action: str, args: dict[str, Any]) -> Any:
        return self._client.call(self._server, self._tool, args)


class MCPHub:
    """MCP yaşam-döngüsü yöneticisi. Sağlıklı sunucuların araçlarını capability+executor olarak bağlar."""

    def __init__(self, client: Optional[MCPClient] = None) -> None:
        self._client = client
        self._servers: dict[str, MCPServer] = {}

    def register_client(self, client: MCPClient) -> None:
        self._client = client

    def register_server(self, server: MCPServer) -> MCPServer:
        self._servers[server.id] = server
        return server

    def list_servers(self) -> list[MCPServer]:
        return list(self._servers.values())

    def get_server(self, server_id: str) -> Optional[MCPServer]:
        return self._servers.get(server_id)

    def remove_server(self, server_id: str) -> bool:
        """Bir MCP sunucusunu kayıttan düşürür (MCP Management Domain için; additive/backward-compatible)."""
        return self._servers.pop(server_id, None) is not None

    # -- Discovery ---------------------------------------------------------- #
    def discover(self) -> int:
        """İstemciyle sunucuları keşfeder + araçlarını listeler. İstemci yoksa 0 (dürüst)."""
        if self._client is None:
            return 0
        found = 0
        for server in self._client.discover():
            if not server.tools:
                try:
                    server.tools = self._client.list_tools(server)
                except Exception:  # noqa: BLE001
                    server.tools = []
            self.register_server(server)
            found += 1
        return found

    # -- Health Check ------------------------------------------------------- #
    def health_check(self) -> dict[str, str]:
        """Her sunucunun sağlığını günceller. İstemci yoksa durum 'unknown' kalır (dürüst)."""
        out: dict[str, str] = {}
        for s in self._servers.values():
            if self._client is not None:
                try:
                    s.status = self._client.health(s)
                except Exception:  # noqa: BLE001
                    s.status = ServerStatus.DOWN
                s.last_health_at = now_iso()
            out[s.name] = s.status
        return out

    # -- Capability Mapping + Executor Binding ------------------------------ #
    def map_and_bind(self, capabilities: CapabilityRegistry, orchestrator: ToolOrchestrator, *,
                     on_capability=None) -> int:
        """Yalnız SAĞLIKLI sunucuların araçlarını Capability'ye haritalar (manifest+risk) + orchestrator'a
        executor bağlar. Sağlıksız/bilinmeyen sunucu → bağlanmaz (dürüst). `on_capability(server, cap)` her
        bağlanan yetenek için çağrılır (Capability Discovery pipeline'ı Executive'e rapor + index için kullanır).
        RİSK-KAPILI İZİN: yüksek-riskli araç ya da GÜVENİLMEYEN sunucu → kullanıcı onayı gerektirir."""
        if self._client is None:
            return 0
        bound = 0
        for s in self._servers.values():
            if s.status != ServerStatus.HEALTHY:
                continue
            for tool in s.tools:
                needs_approval = (tool.requires_user_approval
                                  or tool.risk_level == RiskLevel.HIGH
                                  or s.trust_level == TrustLevel.UNTRUSTED and tool.risk_level != RiskLevel.LOW)
                cap = Capability(
                    name=f"{s.name}.{tool.name}",
                    description=tool.description or f"MCP {s.name} · {tool.name}",
                    can_do=[tool.name], risk_level=tool.risk_level,
                    required_permissions=list(tool.required_permissions),
                    usable_by_brains=list(tool.usable_by_brains),
                    incurs_cost=tool.incurs_cost, requires_user_approval=needs_approval,
                    source="mcp", parameters=dict(tool.input_schema), provenance=s.name,
                    category=infer_category(tool.name))
                capabilities.register(cap)
                orchestrator.register_executor(cap.name, _MCPExecutor(self._client, s, tool.name))
                bound += 1
                if on_capability is not None:
                    on_capability(s, cap)
        return bound

    def activate(self, capabilities: CapabilityRegistry, orchestrator: ToolOrchestrator) -> dict[str, int]:
        """İlk açılış tam akışı: discover → health_check → map_and_bind. 'Neleri yapabilirim' dolar."""
        discovered = self.discover()
        self.health_check()
        bound = self.map_and_bind(capabilities, orchestrator)
        return {"discovered_servers": discovered, "bound_capabilities": bound,
                "healthy_servers": sum(1 for s in self._servers.values()
                                       if s.status == ServerStatus.HEALTHY)}

    def summary(self) -> dict[str, Any]:
        return {"servers": [s.to_dict() for s in self._servers.values()],
                "healthy": sum(1 for s in self._servers.values() if s.status == ServerStatus.HEALTHY)}
