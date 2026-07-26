"""MIO Core · Ekosistem servisleri — Marketplace/Recommendation/AutoInstaller/Store/Diagnostics/
Analytics/PolicyProfiles (Öncelik 4-10). Üretim testleri, deterministik, LLM-siz."""

import pytest

from mio_core.adapters.mcp_client import MCPServerConfig, StdioMCPClient
from mio_core.capability import Capability, CapabilityRegistry, RiskLevel
from mio_core.events import Ev, EventBus
from mio_core.execution import (
    AutoInstaller,
    CapabilityAnalytics,
    CapabilityDiscovery,
    CapabilityMarketplace,
    MCPStore,
    MetaMCPManager,
    PolicyProfiles,
    RecommendationEngine,
    SelfDiagnostics,
    ToolOrchestrator,
    VersionManager,
    default_marketplace,
)


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


def _market():
    m = CapabilityMarketplace()
    m.add_all(default_marketplace())
    return m


# ---- Marketplace + Recommendation (5, 7) ----
def test_marketplace_search_and_list():
    m = _market()
    assert m.get("filesystem") and m.get("stripe").requires_key
    assert any(e.name == "playwright" for e in m.list("browser_automation"))
    assert m.search("web arama")                          # brave-search/fetch


def test_recommendation_for_missing_category():
    caps = CapabilityRegistry()
    rec = RecommendationEngine(_market(), caps)
    opts = rec.recommend_for_category("browser_automation")
    assert any(e.name == "playwright" for e in opts)      # eksik → öner
    # kategori bağlıysa önermez
    caps.register(Capability("pw.navigate", category="browser_automation", connected=True, source="mcp"))
    assert rec.recommend_for_category("browser_automation") == []


# ---- Auto Installer (4) ----
def test_auto_installer_flow():
    caps = CapabilityRegistry()
    orch = ToolOrchestrator(caps)
    disco = CapabilityDiscovery(caps, orch)
    bus = EventBus(record=True)
    installed_config = MCPServerConfig("filesystem", command=["x"])

    def fake_installer(entry):                            # GERÇEK kurulumun yerine test double
        return installed_config

    ai = AutoInstaller(_market(), disco, installer=fake_installer, bus=bus,
                       client_factory=lambda cfgs: StdioMCPClient(
                           cfgs, transport_factory=lambda c: FakeTransport([{"name": "read_file"}])))
    res = ai.install("filesystem", user_approved=True)
    assert res.status == "installed" and res.capabilities == 1
    assert caps.can("filesystem.read_file")
    assert any(e["type"] == Ev.INSTALL for e in bus.history())


def test_auto_installer_needs_approval_and_no_installer():
    ai = AutoInstaller(_market(), None)
    assert ai.install("stripe").status == "needs_approval"     # yüksek risk + anahtar
    assert ai.install("filesystem").status == "no_installer"   # onay ok ama installer yok (dürüst)
    assert ai.install("yok").status == "not_found"


# ---- MCP Store + Diagnostics + Analytics (6, 8, 9) ----
def _wired():
    caps = CapabilityRegistry()
    orch = ToolOrchestrator(caps)
    disco = CapabilityDiscovery(caps, orch)
    disco.discover(StdioMCPClient([MCPServerConfig("fs", command=["x"])],
                                  transport_factory=lambda c: FakeTransport(
                                      [{"name": "read_file"}, {"name": "delete_file"}])))
    meta = MetaMCPManager(caps)
    meta.attach(orch)
    from mio_core.execution import ToolRequest
    orch.execute(ToolRequest("fs.read_file", "read", {}, requester="Engineering"))
    return caps, orch, meta


def test_mcp_store_state():
    caps, _orch, meta = _wired()
    st = MCPStore(caps, meta).state()
    fs = next(s for s in st if s["server"] == "fs")
    assert fs["capability_count"] == 2 and fs["connected"] == 2 and fs["calls"] >= 1


def test_self_diagnostics():
    caps, _orch, meta = _wired()
    vm = VersionManager(); vm.register("fs", "1.0"); vm.set_latest("fs", "1.1")
    rep = SelfDiagnostics(caps, meta, versions=vm).run()
    assert rep["connected"] == 2 and rep["categories"] >= 1
    assert "fs.delete_file" in rep["unused_capabilities"]      # hiç çağrılmadı
    assert "fs" in rep["outdated"]


def test_capability_analytics():
    caps, _orch, meta = _wired()
    rep = CapabilityAnalytics(caps, meta).report()
    assert rep["most_used"] == "fs.read_file" and rep["total_calls"] >= 1


# ---- Policy Profiles (10) ----
def test_policy_profiles():
    pp = PolicyProfiles()
    assert set(pp.names()) >= {"safe", "read_only", "offline", "autonomous", "high_security"}
    high_risk = Capability("x.delete", risk_level=RiskLevel.HIGH)
    pp.activate("read_only")
    ok, _, reason = pp.evaluate(high_risk)
    assert not ok and "salt-okunur" in reason
    pp.activate("offline")
    ok2, _, _ = pp.evaluate(Capability("s.msg", category="messaging"))
    assert not ok2                                            # çevrimdışı → ağ bloklu
    pp.activate("autonomous")
    ok3, needs_user, _ = pp.evaluate(high_risk)
    assert ok3 and not needs_user                            # otonom → onay gevşek
    pp.activate("high_security")
    ok4, _, _ = pp.evaluate(high_risk)
    assert not ok4                                           # yüksek güvenlik → high risk bloklu


# ---- Federation (11) — mimari-hazır ----
def test_federation_aggregates_providers():
    from mio_core.execution import FederatedCapabilities, LocalProvider
    r1 = CapabilityRegistry(); r1.register(Capability("a", category="db", connected=True))
    r2 = CapabilityRegistry(); r2.register(Capability("a", category="db", connected=True))
    fed = FederatedCapabilities()
    fed.add_provider(LocalProvider(r1, node="desktop"))
    fed.add_provider(LocalProvider(r2, node="server"))
    assert set(fed.nodes()) == {"desktop", "server"}
    assert len(fed.find("a")) == 2                            # aynı yetenek iki düğümde (load-balance temeli)
