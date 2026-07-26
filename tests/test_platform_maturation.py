"""MIO Core · Platform olgunlaştırma — Event Bus + Sandbox + Version Manager (üretim testleri)."""

import pytest

from mio_core.adapters.mcp_client import MCPServerConfig, StdioMCPClient
from mio_core.capability import CapabilityRegistry
from mio_core.events import Ev, EventBus
from mio_core.execution import (
    CapabilityDiscovery,
    SandboxPipeline,
    ToolOrchestrator,
    VersionManager,
)


class FakeTransport:
    def __init__(self, tools, result="ok", healthy=True):
        self._tools = tools
        self._result = result
        self._healthy = healthy

    def request(self, method, params=None):
        if method == "tools/list":
            return {"tools": self._tools}
        if method == "tools/call":
            return {"content": [{"type": "text", "text": self._result}]}
        return {}

    def is_alive(self):
        return self._healthy

    def close(self):
        pass


def _client(tools):
    return StdioMCPClient([MCPServerConfig("fs", command=["x"])],
                          transport_factory=lambda c: FakeTransport(tools))


# ---- Event Bus (Öncelik 12) ----
def test_event_bus_pub_sub():
    bus = EventBus(record=True)
    seen = []
    bus.subscribe(Ev.DIAGNOSTIC, lambda e: seen.append(e["data"]))
    allseen = []
    bus.subscribe_all(lambda e: allseen.append(e["type"]))
    bus.publish(Ev.DIAGNOSTIC, {"x": 1})
    bus.publish(Ev.ANALYTICS, {"y": 2})
    assert seen == [{"x": 1}]                              # tip-filtreli abone
    assert allseen == [Ev.DIAGNOSTIC, Ev.ANALYTICS]       # tüm-abone
    assert len(bus.history()) == 2
    assert len(bus.history(Ev.DIAGNOSTIC)) == 1


def test_event_bus_subscriber_error_does_not_break():
    bus = EventBus()
    bus.subscribe(Ev.DIAGNOSTIC, lambda e: 1 / 0)          # patlar
    ok = []
    bus.subscribe(Ev.DIAGNOSTIC, lambda e: ok.append(True))
    bus.publish(Ev.DIAGNOSTIC)                             # bus durmamalı
    assert ok == [True]


# ---- Sandbox (Öncelik 2) ----
def test_sandbox_approves_low_risk():
    bus = EventBus(record=True)
    report = SandboxPipeline(bus=bus).evaluate(_client([{"name": "read_file"}]))
    assert report.verdict == "approved"                   # düşük risk, onay gerekmez
    assert report.capabilities == 1
    stage_names = {s.stage for s in report.stages}
    assert {"identity_verification", "manifest_validation", "security_scan",
            "policy_validation", "capability_extraction"} <= stage_names
    assert any(e["type"] == Ev.SANDBOX_RESULT for e in bus.history())


def test_sandbox_flags_high_risk_needs_approval():
    report = SandboxPipeline().evaluate(_client([{"name": "delete_repo"}]))
    assert report.verdict == "needs_approval"             # yüksek risk → onay
    assert "fs.delete_repo" in report.needs_approval


def test_sandbox_rejects_unhealthy():
    client = StdioMCPClient([MCPServerConfig("bad", command=["x"])],
                            transport_factory=lambda c: FakeTransport([], healthy=False))
    report = SandboxPipeline().evaluate(client)
    assert report.verdict == "rejected"                   # sağlıksız → production'a girmez


def test_sandbox_promote_only_when_not_rejected():
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    disco = CapabilityDiscovery(reg, orch)
    client = _client([{"name": "read_file"}])
    result = SandboxPipeline().promote(client, disco)
    assert result is not None and reg.can("fs.read_file")  # onaylandı → production'a promote edildi


# ---- Version Manager (Öncelik 3) ----
def test_version_manager_recommendations():
    vm = VersionManager()
    vm.register("github", current="1.0.0")
    assert vm.recommendation("github") == "unknown"       # latest bilinmiyor
    vm.set_latest("github", "1.1.0")
    assert vm.recommendation("github") == "update"        # güncel değil, breaking yok
    vm.set_latest("github", "2.0.0", breaking=True)
    assert vm.recommendation("github") == "suggest"       # breaking → öner
    vm.set_latest("github", "1.0.0")                       # latest == current
    assert vm.recommendation("github") == "up_to_date"
    vm.register("old", current="0.1", deprecated=True)
    assert vm.recommendation("old") == "block"            # deprecated → engelle


def test_version_manager_publishes_event():
    bus = EventBus(record=True)
    vm = VersionManager(bus=bus)
    vm.register("x", current="1.0")
    vm.set_latest("x", "2.0")
    assert any(e["type"] == Ev.VERSION_UPDATE for e in bus.history())
