"""MIO Core · MCP Hub — üretim testleri (deterministik, çekirdek LLM-siz).

Discovery + health + capability mapping + executor binding + orchestrator entegrasyonu. MCP transport
GERÇEK adaptör test double'ıdır; çekirdek ağ yapmaz.
"""

import pytest

from mio_core.brains import BrainRegistry, default_domain_brains
from mio_core.capability import CapabilityRegistry, RiskLevel
from mio_core.execution import (
    MCPHub,
    MCPServer,
    MCPTool,
    ServerStatus,
    ToolOrchestrator,
    ToolRequest,
    TrustLevel,
)
from mio_core.executive import ExecutiveState, SQLiteExecutiveStateStore
from mio_core.self_awareness import SelfAwareness


class FakeMCPClient:
    def __init__(self, servers, health_map, call_result="mcp-ok"):
        self._servers = servers
        self._health = health_map
        self._call_result = call_result
        self.calls = []

    def discover(self):
        return list(self._servers)

    def list_tools(self, server):
        return server.tools

    def health(self, server):
        return self._health.get(server.name, ServerStatus.UNKNOWN)

    def call(self, server, tool_name, args):
        self.calls.append((server.name, tool_name, args))
        return self._call_result


def _setup(call_result="mcp-ok"):
    gh = MCPServer("github", version="1.2.0", trust_level=TrustLevel.VERIFIED, tools=[
        MCPTool("create_issue", risk_level=RiskLevel.MEDIUM, usable_by_brains=["Engineering"]),
        MCPTool("delete_repo", risk_level=RiskLevel.HIGH, requires_user_approval=True),
    ])
    bad = MCPServer("bad", tools=[MCPTool("x")])
    client = FakeMCPClient([gh, bad], {"github": ServerStatus.HEALTHY, "bad": ServerStatus.DOWN},
                           call_result=call_result)
    return client


def test_discover_and_health():
    hub = MCPHub(_setup())
    assert hub.discover() == 2
    statuses = hub.health_check()
    assert statuses["github"] == "healthy" and statuses["bad"] == "down"


def test_only_healthy_servers_bound():
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    result = MCPHub(_setup()).activate(reg, orch)
    assert result["discovered_servers"] == 2 and result["healthy_servers"] == 1
    assert result["bound_capabilities"] == 2                     # github'ın 2 aracı
    assert reg.can("github.create_issue") and reg.can("github.delete_repo")
    assert reg.get("bad.x") is None                              # sağlıksız sunucu → bağlanmadı (dürüst)


def test_execute_mcp_tool_via_orchestrator():
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    client = _setup(call_result="issue#42")
    MCPHub(client).activate(reg, orch)
    res = orch.execute(ToolRequest("github.create_issue", "create", {"title": "bug"},
                                   requester="Engineering"))
    assert res.success and res.output == "issue#42"
    assert client.calls[-1] == ("github", "create_issue", {"title": "bug"})


def test_mcp_tool_usable_by_restriction():
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    MCPHub(_setup()).activate(reg, orch)
    res = orch.execute(ToolRequest("github.create_issue", "create", {}, requester="Finance"))
    assert res.blocked and "kullanamaz" in res.reason           # yalnız Engineering


def test_mcp_high_risk_requires_approval():
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    MCPHub(_setup()).activate(reg, orch)
    res = orch.execute(ToolRequest("github.delete_repo", "delete", {}, requester="Executive"))
    assert res.blocked and res.verdict == "await_approval"      # onay kapısı


def test_no_client_is_honest():
    hub = MCPHub()
    assert hub.discover() == 0
    assert hub.map_and_bind(CapabilityRegistry(), ToolOrchestrator(CapabilityRegistry())) == 0


def test_self_awareness_reflects_mcp():
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    MCPHub(_setup()).activate(reg, orch)
    state = ExecutiveState(SQLiteExecutiveStateStore(":memory:"))
    state.ensure_identity("MIO")
    brains = BrainRegistry()
    brains.register_all(default_domain_brains())
    model = SelfAwareness(state, brains, reg).self_model()
    assert set(model["active_mcps"]) == {"github.create_issue", "github.delete_repo"}
    assert "github.create_issue" in model["capabilities"]["connected"]
