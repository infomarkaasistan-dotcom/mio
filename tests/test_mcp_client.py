"""MIO Core · Gerçek MCP client — üretim testleri (transport test double ile; protokol mantığı gerçek)."""

import pytest

from mio_core.adapters.mcp_client import MCPServerConfig, StdioMCPClient, infer_risk
from mio_core.capability import CapabilityRegistry, RiskLevel
from mio_core.execution import MCPHub, ToolOrchestrator, ToolRequest


class FakeTransport:
    def __init__(self, tools, *, call_result="ok", alive=True, is_error=False):
        self._tools = tools
        self._call_result = call_result
        self._alive = alive
        self._is_error = is_error
        self.calls = []

    def request(self, method, params=None):
        if method == "tools/list":
            return {"tools": self._tools}
        if method == "tools/call":
            self.calls.append((params["name"], params["arguments"]))
            if self._is_error:
                return {"isError": True, "content": [{"type": "text", "text": "boom"}]}
            return {"content": [{"type": "text", "text": self._call_result}]}
        return {}

    def is_alive(self):
        return self._alive

    def close(self):
        pass


_TOOLS = [{"name": "read_file", "description": "dosya oku"},
          {"name": "delete_file", "description": "dosya sil"}]


def test_infer_risk():
    assert infer_risk("delete_repo") == RiskLevel.HIGH
    assert infer_risk("read_file") == RiskLevel.LOW
    assert infer_risk("frobnicate") == RiskLevel.MEDIUM


def test_discover_maps_tools_and_risk():
    ft = FakeTransport(_TOOLS)
    client = StdioMCPClient([MCPServerConfig("fs", command=["x"])], transport_factory=lambda c: ft)
    servers = client.discover()
    assert servers[0].status == "healthy"
    risks = {t.name: t.risk_level for t in servers[0].tools}
    assert risks == {"read_file": RiskLevel.LOW, "delete_file": RiskLevel.HIGH}


def test_call_extracts_text_content():
    ft = FakeTransport(_TOOLS, call_result="dosya içeriği")
    client = StdioMCPClient([MCPServerConfig("fs", command=["x"])], transport_factory=lambda c: ft)
    s = client.discover()[0]
    out = client.call(s, "read_file", {"path": "a.txt"})
    assert out == "dosya içeriği"
    assert ft.calls[-1] == ("read_file", {"path": "a.txt"})


def test_call_is_error_raises():
    ft = FakeTransport(_TOOLS, is_error=True)
    client = StdioMCPClient([MCPServerConfig("fs", command=["x"])], transport_factory=lambda c: ft)
    s = client.discover()[0]
    with pytest.raises(RuntimeError):
        client.call(s, "read_file", {})


def test_server_start_failure_is_down():
    def boom(_c):
        raise RuntimeError("npx bulunamadı")
    client = StdioMCPClient([MCPServerConfig("fs", command=["x"])], transport_factory=boom)
    assert client.discover()[0].status == "down"


def test_health_down_when_process_dead():
    ft = FakeTransport(_TOOLS, alive=False)
    client = StdioMCPClient([MCPServerConfig("fs", command=["x"])], transport_factory=lambda c: ft)
    s = client.discover()[0]
    assert client.health(s) == "down"


# ---- MCP Hub → Capability → Orchestrator (gerçek uçtan uca akış) ----
def test_mcp_client_through_hub_and_orchestrator():
    ft = FakeTransport(_TOOLS, call_result="okundu")
    client = StdioMCPClient([MCPServerConfig("fs", command=["x"])], transport_factory=lambda c: ft)
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    result = MCPHub(client).activate(reg, orch)
    assert result["bound_capabilities"] == 2
    assert reg.can("fs.read_file") and reg.can("fs.delete_file")
    res = orch.execute(ToolRequest("fs.read_file", "read", {"path": "a"}, requester="Engineering"))
    assert res.success and res.output == "okundu"
    assert ft.calls[-1] == ("read_file", {"path": "a"})
