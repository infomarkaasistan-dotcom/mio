"""MIO Core · Capability Management Domain (Faz 2 · Domain 16) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek CapabilityRegistry + SQLite state/lifecycle deposu üzerinden. §7 maturity
geçişleri, deterministik seçim, kalıcı override restore, evolution denetimi, authorization, events ve uçtan-uca
akış doğrulanır."""

import pytest

from mio_core.capability import Capability, CapabilityRegistry, MaturityLevel
from mio_core.domains.capability_mgmt import (
    CapabilityManagementDomain,
    CapabilityRepository,
    CapEvents,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(seed=True):
    reg = CapabilityRegistry()
    if seed:
        reg.register(Capability(name="search_a", category="web_search", maturity=MaturityLevel.STABLE,
                                priority=40, connected=True))
        reg.register(Capability(name="search_b", category="web_search", maturity=MaturityLevel.PRODUCTION,
                                priority=30, connected=True))
        reg.register(Capability(name="search_c", category="web_search", maturity=MaturityLevel.EXPERIMENTAL,
                                priority=99, connected=False))
    repo = CapabilityRepository(":memory:")
    bus = EventBus(record=True)
    dom = CapabilityManagementDomain(reg, repo, bus=bus)
    return dom, reg, repo, bus


@pytest.fixture
def cm():
    return _build()


# ---- UNIT: register validation + authorization ----
def test_register_validation_and_admin(cm):
    d, _r, _rp, _b = cm
    d.register("owner", "new_cap", "yeni", maturity=MaturityLevel.PREVIEW)
    with pytest.raises(ValidationError):
        d.register("owner", "new_cap", "tekrar")               # zaten kayıtlı
    with pytest.raises(ValidationError):
        d.register("owner", "x", maturity="uydurma")
    with pytest.raises(UnauthorizedError):
        d.register("Reasoning", "y")                           # reader ama admin değil
    with pytest.raises(UnauthorizedError):
        d.describe("yabanci", "search_a")


# ---- INTEGRATION: §7 maturity yaşam-döngüsü ----
def test_maturity_lifecycle_valid_and_invalid(cm):
    d, _r, _rp, bus = cm
    d.register("owner", "cap1", maturity=MaturityLevel.EXPERIMENTAL)
    assert d.set_maturity("owner", "cap1", MaturityLevel.PREVIEW)["maturity"] == MaturityLevel.PREVIEW
    d.set_maturity("owner", "cap1", MaturityLevel.STABLE)
    d.set_maturity("owner", "cap1", MaturityLevel.PRODUCTION)
    with pytest.raises(ValidationError):
        d.set_maturity("owner", "cap1", MaturityLevel.EXPERIMENTAL)   # geri gidiş yok
    d.retire("owner", "cap1")
    with pytest.raises(ValidationError):
        d.set_maturity("owner", "cap1", MaturityLevel.STABLE)         # retired terminal
    assert any(e["type"] == CapEvents.MATURITY_CHANGED for e in bus.history())


def test_maturity_noop_idempotent(cm):
    d, _r, _rp, _b = cm
    out = d.set_maturity("owner", "search_a", MaturityLevel.STABLE)   # zaten stable
    assert out["maturity"] == MaturityLevel.STABLE


# ---- INTEGRATION: deterministik yetenek seçimi ----
def test_select_best_deterministic(cm):
    d, _r, _rp, bus = cm
    best = d.select_best("owner", "web_search")
    assert best["name"] == "search_b"                          # PRODUCTION > STABLE (maturity sırası)
    assert best == d.select_best("owner", "web_search")        # determinizm
    # search_c EXPERIMENTAL ama connected=False → seçilmez
    assert d.select_best("owner", "yok-kategori") is None
    assert any(e["type"] == CapEvents.SELECTED for e in bus.history())


def test_usable_reflects_maturity_and_connection(cm):
    d, _r, _rp, _b = cm
    assert d.usable("owner", "search_b") is True
    assert d.usable("owner", "search_c") is False              # connected değil
    d.retire("owner", "search_a")
    assert d.usable("owner", "search_a") is False              # retired → USABLE değil


# ---- INTEGRATION: set_connected + describe + list filtreleri ----
def test_connected_describe_and_filters(cm):
    d, _r, _rp, bus = cm
    d.set_connected("owner", "search_c", True)
    assert d.describe("owner", "search_c")["connected"] is True
    prod = d.list_capabilities("owner", maturity=MaturityLevel.PRODUCTION)
    assert [c["name"] for c in prod] == ["search_b"]
    with pytest.raises(NotFoundError):
        d.describe("owner", "yok")
    assert any(e["type"] == CapEvents.CONNECTED for e in bus.history())


# ---- INTEGRATION: kalıcılık (restore) + evolution denetimi ----
def test_persistence_restore_and_lifecycle():
    reg1 = CapabilityRegistry()
    reg1.register(Capability(name="cap_x", maturity=MaturityLevel.EXPERIMENTAL))
    repo = CapabilityRepository(":memory:")
    d1 = CapabilityManagementDomain(reg1, repo)
    d1.set_maturity("owner", "cap_x", MaturityLevel.PREVIEW)   # kalıcılaşır
    # yeniden başlatma: taze registry (born capable) + aynı repo → restore override'ı uygular
    reg2 = CapabilityRegistry()
    reg2.register(Capability(name="cap_x", maturity=MaturityLevel.EXPERIMENTAL))
    d2 = CapabilityManagementDomain(reg2, repo)
    d2.restore("owner")
    assert reg2.get("cap_x").maturity == MaturityLevel.PREVIEW
    assert any(h["kind"] == "maturity_changed" for h in d2.lifecycle_history("owner", name="cap_x"))


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(cm):
    d, _r, _rp, _b = cm
    s = d.stats()
    assert s["total"] == 3 and s["usable"] == 2 and s["by_maturity"]["production"] == 1
    assert s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "capability_management" and "select_best" in c["operations"]


# ---- SMOKE: boot() → çekirdek registry sarılı, gerçek innate yetenekler ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    caps = mio.capability_management.list_capabilities("owner")
    assert len(caps) >= 1                                       # doğuştan/keşfedilen yetenekler
    # ham registry ile aynı doğruluk kaynağı
    assert len(caps) == len(mio.capabilities.list())
    st = mio.capability_management.stats()
    assert st["total"] == len(mio.capabilities.list())
    assert mio.capability_management.contract()["version"] == "1.0.0"
    mio.close()
