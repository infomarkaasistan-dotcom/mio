"""MIO Core · MCP Management Domain (Faz 2 · Domain 17) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek MCPHub + gerçek ToolOrchestrator/CapabilityRegistry + SQLite kayıt üzerinden.
Trust yaşam-döngüsü (Madde 24), aktivasyon + trust kapısı, kalıcılık/restore, authorization, events ve
uçtan-uca akış doğrulanır. Ağ yok — enjekte edilen deterministik FakeMCPClient."""

import pytest

from mio_core.capability import CapabilityRegistry, RiskLevel
from mio_core.domains.mcp_mgmt import (
    MCPManagementDomain,
    MCPRepository,
    MCPEvents,
    ServerStatus,
    TrustLevel,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus
from mio_core.execution.mcp_hub import MCPHub, MCPServer, MCPTool
from mio_core.execution.orchestrator import ToolOrchestrator, ToolRequest


class _FakeMCPClient:
    def __init__(self, servers): self._servers = servers
    def discover(self): return list(self._servers)
    def list_tools(self, server): return server.tools
    def health(self, server): return ServerStatus.HEALTHY
    def call(self, server, tool_name, args): return {"tool": tool_name, "args": args}


def _build(client=None):
    hub = MCPHub(client)
    repo = MCPRepository(":memory:")
    caps = CapabilityRegistry()
    orch = ToolOrchestrator(caps)
    bus = EventBus(record=True)
    dom = MCPManagementDomain(hub, repo, capabilities=caps, orchestrator=orch, bus=bus)
    return dom, hub, repo, caps, orch, bus


@pytest.fixture
def mm():
    return _build()


# ---- UNIT: register validation + authorization ----
def test_register_validation_and_admin(mm):
    d, _h, _r, _c, _o, _b = mm
    with pytest.raises(ValidationError):
        d.register_server("owner", "  ")
    with pytest.raises(ValidationError):
        d.register_server("owner", "s", transport="carrier-pigeon")
    with pytest.raises(ValidationError):
        d.register_server("owner", "s", trust_level="süper")
    with pytest.raises(UnauthorizedError):
        d.register_server("Engineering", "s")                 # reader ama admin değil
    with pytest.raises(UnauthorizedError):
        d.describe("yabanci", "x")


# ---- INTEGRATION: trust yaşam-döngüsü ----
def test_trust_lifecycle(mm):
    d, _h, _r, _c, _o, bus = mm
    s = d.register_server("owner", "github", transport="stdio")   # varsayılan untrusted
    assert s["trust_level"] == TrustLevel.UNTRUSTED
    upd = d.set_trust("Security", s["id"], TrustLevel.VERIFIED)   # Security admin
    assert upd["trust_level"] == TrustLevel.VERIFIED
    assert d.describe("owner", s["id"])["trust_level"] == TrustLevel.VERIFIED
    assert any(e["type"] == MCPEvents.TRUST_CHANGED for e in bus.history())
    with pytest.raises(ValidationError):
        d.set_trust("owner", s["id"], "uydurma")
    with pytest.raises(NotFoundError):
        d.set_trust("owner", "yok-id", TrustLevel.TRUSTED)


# ---- INTEGRATION: aktivasyon + trust kapısı (Madde 24) ----
def test_activate_binds_and_trust_gates():
    trusted = MCPServer(name="fs", trust_level=TrustLevel.TRUSTED,
                        tools=[MCPTool(name="read_file", risk_level=RiskLevel.LOW)])
    untrusted = MCPServer(name="shady", trust_level=TrustLevel.UNTRUSTED,
                          tools=[MCPTool(name="run_shell", risk_level=RiskLevel.MEDIUM)])
    d, _h, _r, caps, _o, bus = _build(_FakeMCPClient([trusted, untrusted]))
    report = d.activate("owner")
    assert report["bound_capabilities"] >= 2                  # her iki sağlıklı sunucunun aracı bağlandı
    assert "shady" in report["trust_gated_servers"]           # untrusted → trust kapılı (görünür)
    # untrusted + riskli araç → yürütme kullanıcı onayı ister (çekirdek trust kapısı)
    assert caps.get("shady.run_shell").requires_user_approval is True
    assert caps.get("fs.read_file").requires_user_approval is False
    assert any(e["type"] == MCPEvents.ACTIVATED for e in bus.history())


def test_activate_requires_wiring():
    hub = MCPHub(None)
    d = MCPManagementDomain(hub, MCPRepository(":memory:"))    # caps/orch YOK
    with pytest.raises(ValidationError):
        d.activate("owner")


# ---- INTEGRATION: discover + health (istemcisiz dürüst) ----
def test_discover_and_health_honest_without_client(mm):
    d, _h, _r, _c, _o, _b = mm                                # client yok
    assert d.discover("owner")["discovered"] == 0             # dürüst: istemci yok → 0
    d.register_server("owner", "s1")
    assert d.health_check("owner")["s1"] == ServerStatus.UNKNOWN   # istemci yok → unknown


# ---- INTEGRATION: kalıcılık (restore) + remove ----
def test_persistence_restore_and_remove():
    hub1 = MCPHub(None)
    repo = MCPRepository(":memory:")
    d1 = MCPManagementDomain(hub1, repo)
    s = d1.register_server("owner", "persistent", trust_level=TrustLevel.TRUSTED)
    # yeniden başlatma: taze hub + aynı repo → restore
    hub2 = MCPHub(None)
    d2 = MCPManagementDomain(hub2, repo)
    d2.restore("owner")
    assert hub2.get_server(s["id"]) is not None
    assert d2.describe("owner", s["id"])["trust_level"] == TrustLevel.TRUSTED
    d2.remove_server("owner", s["id"])
    assert hub2.get_server(s["id"]) is None
    with pytest.raises(NotFoundError):
        d2.describe("owner", s["id"])


# ---- INTEGRATION: list + stats + contract ----
def test_list_stats_contract(mm):
    d, _h, _r, _c, _o, _b = mm
    d.register_server("owner", "a", trust_level=TrustLevel.TRUSTED)
    d.register_server("owner", "b", trust_level=TrustLevel.UNTRUSTED)
    assert len(d.list_servers("owner", trust_level=TrustLevel.TRUSTED)) == 1
    s = d.stats()
    assert s["servers"] == 2 and s["by_trust"]["trusted"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "mcp_management" and "activate" in c["operations"]


# ---- SMOKE: boot() → çekirdek MCPHub sarılı ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    s = mio.mcp_management.register_server("owner", "smoke-mcp", trust_level=TrustLevel.TRUSTED)
    assert any(x["id"] == s["id"] for x in mio.mcp_management.list_servers("owner"))
    # ham hub ile aynı doğruluk kaynağı
    assert mio.mcp_hub.get_server(s["id"]) is not None
    assert mio.mcp_management.stats()["servers"] >= 1
    assert mio.mcp_management.contract()["version"] == "1.0.0"
    mio.close()
