"""MIO Core · MCP client — TRANSPORT-AGNOSTİK (üretim), stdlib-only.

Herhangi bir MCP sunucusuna bağlanır: initialize → tools/list (keşif) → tools/call (yürütme). Transportu
BİLMEZ — `transport.py`'deki plugin katmanından (stdio/http/https/sse/...) `build_transport(config)` ile alır.
Böylece transport değişince bu istemci ve üstündeki hiçbir katman değişmez.

Transport (subprocess/HTTP) enjekte edilebilir → protokol mantığı gerçek sunucu olmadan test edilir.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from mio_core.adapters.transport import (
    JsonRpcError,
    MCPServerConfig,
    MCPTransport,
    StdioTransport,
    build_transport,
)
from mio_core.capability import RiskLevel
from mio_core.execution.mcp_hub import MCPServer, MCPTool, ServerStatus

__all__ = ["MCPServerConfig", "JsonRpcError", "MCPTransport", "StdioTransport",
           "StdioMCPClient", "infer_risk"]

_DESTRUCTIVE = ("delete", "remove", "drop", "write", "exec", "run", "kill", "push", "deploy", "pay")
_READONLY = ("read", "list", "get", "search", "fetch", "query", "view", "describe")


def infer_risk(tool_name: str) -> str:
    low = tool_name.lower()
    if any(t in low for t in _DESTRUCTIVE):
        return RiskLevel.HIGH
    if any(t in low for t in _READONLY):
        return RiskLevel.LOW
    return RiskLevel.MEDIUM


TransportFactory = Callable[[MCPServerConfig], MCPTransport]


def _extract_content(result: dict) -> Any:
    """MCP tools/call sonucundan içeriği çıkarır ({"content":[{"type":"text","text":...}]})."""
    content = result.get("content")
    if isinstance(content, list):
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        if texts:
            return "\n".join(texts)
        return content
    return result


class StdioMCPClient:
    """MCP Hub'ın kullandığı transport-agnostik istemci (ad geriye-uyum için 'Stdio' — artık her transport).
    `transport_factory` verilmezse `build_transport` kullanılır (config.transport'a göre stdio/http/sse/...)."""

    def __init__(self, configs: list[MCPServerConfig], *,
                 transport_factory: Optional[TransportFactory] = None) -> None:
        self._configs = {c.name: c for c in configs}
        self._factory = transport_factory or build_transport
        self._transports: dict[str, MCPTransport] = {}     # server.id -> transport

    def discover(self) -> list[MCPServer]:
        out: list[MCPServer] = []
        for name, cfg in self._configs.items():
            server = MCPServer(name=name, transport=cfg.transport, trust_level=cfg.trust_level)
            try:
                tr = self._factory(cfg)
                self._transports[server.id] = tr
                server.tools = self._list_tools_via(tr)
                server.status = ServerStatus.HEALTHY
            except Exception:  # noqa: BLE001 — sunucu başlatılamadı/çöktü → dürüstçe DOWN
                server.status = ServerStatus.DOWN
            out.append(server)
        return out

    def list_tools(self, server: MCPServer) -> list[MCPTool]:
        tr = self._transports.get(server.id)
        return self._list_tools_via(tr) if tr is not None else []

    def _list_tools_via(self, tr: MCPTransport) -> list[MCPTool]:
        res = tr.request("tools/list")
        tools: list[MCPTool] = []
        for t in res.get("tools", []):
            if not isinstance(t, dict) or not t.get("name"):
                continue
            tools.append(MCPTool(name=t["name"], description=t.get("description", ""),
                                 risk_level=infer_risk(t["name"]),
                                 input_schema=t.get("inputSchema") or {}))
        return tools

    def health(self, server: MCPServer) -> str:
        tr = self._transports.get(server.id)
        if tr is None or not tr.is_alive():
            return ServerStatus.DOWN
        return ServerStatus.HEALTHY

    def call(self, server: MCPServer, tool_name: str, args: dict[str, Any]) -> Any:
        tr = self._transports.get(server.id)
        if tr is None:
            raise RuntimeError(f"MCP sunucusuna bağlı değil: {server.name}")
        res = tr.request("tools/call", {"name": tool_name, "arguments": args})
        if res.get("isError"):
            raise RuntimeError(f"MCP araç hatası: {tool_name} → {_extract_content(res)}")
        return _extract_content(res)

    def close(self) -> None:
        for tr in self._transports.values():
            try:
                tr.close()
            except Exception:  # noqa: BLE001
                pass
