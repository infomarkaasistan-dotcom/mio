"""MIO Core · Capability Discovery pipeline (Meta MCP) — üretim testleri (deterministik, LLM-siz).

Yeni MCP → manifest → risk → capability → Executive rapor → izin. "300 MCP, sıfır kod" iddiasının kanıtı.
"""

import pytest

from mio_core.adapters.mcp_client import MCPServerConfig, StdioMCPClient
from mio_core.capability import CapabilityRegistry
from mio_core.execution import (
    CapabilityDiscovery,
    ToolOrchestrator,
    ToolRequest,
    capability_index,
)
from mio_core.executive import ExecutiveState, SQLiteExecutiveStateStore


class FakeTransport:
    def __init__(self, tools, result="ok"):
        self._tools = tools
        self._result = result

    def request(self, method, params=None):
        if method == "tools/list":
            return {"tools": self._tools}
        if method == "tools/call":
            return {"content": [{"type": "text", "text": self._result}]}
        return {}

    def is_alive(self):
        return True

    def close(self):
        pass


_TOOLS = [
    {"name": "read_file", "description": "dosya oku",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "delete_file", "description": "dosya sil",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}}},
]


def _pipeline(tools=_TOOLS):
    client = StdioMCPClient([MCPServerConfig("fs", command=["x"])],
                            transport_factory=lambda c: FakeTransport(tools))
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    state = ExecutiveState(SQLiteExecutiveStateStore(":memory:"))
    state.ensure_identity("MIO")
    disco = CapabilityDiscovery(reg, orch, state=state)
    return disco.discover(client), reg, orch, state


def test_discover_extracts_capabilities_and_manifest():
    report, reg, _orch, _state = _pipeline()
    assert report.servers_discovered == 1 and report.healthy_servers == 1
    assert {c.name for c in report.capabilities} == {"fs.read_file", "fs.delete_file"}
    # manifest (inputSchema) yakalandı → MIO NASIL çağıracağını bilir
    assert reg.get("fs.read_file").parameters.get("required") == ["path"]
    assert reg.get("fs.read_file").provenance == "fs"


def test_risk_gated_permission():
    report, reg, _o, _s = _pipeline()
    # delete_file → yüksek risk → onay gerekir; read_file → düşük → gerekmez
    assert "fs.delete_file" in report.needs_approval
    assert "fs.read_file" not in report.needs_approval
    assert reg.get("fs.delete_file").requires_user_approval is True


def test_reports_to_executive():
    report, _reg, _orch, state = _pipeline()
    assert report.executive_decision_id
    d = state.get_decision(report.executive_decision_id)
    assert d.kind == "capability_discovery" and "yeni yetenek" in d.chosen


def test_discovered_capability_is_usable():
    report, reg, orch, _s = _pipeline([{"name": "read_file", "description": "oku"}])
    assert reg.can("fs.read_file")
    res = orch.execute(ToolRequest("fs.read_file", "read", {"path": "a"}, requester="Engineering"))
    assert res.success                                    # keşfedilen yetenek hemen kullanılabilir


def test_capability_index_is_meta_catalog():
    _report, reg, _orch, _state = _pipeline()
    idx = capability_index(reg)
    by_name = {e["name"]: e for e in idx}
    assert by_name["fs.delete_file"]["requires_approval"] is True
    assert by_name["fs.read_file"]["source"] == "mcp"
    assert by_name["fs.read_file"]["provenance"] == "fs"
