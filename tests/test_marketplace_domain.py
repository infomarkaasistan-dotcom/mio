"""MIO Core · Marketplace / Ecosystem Domain (Faz 5 · Domain 37) — üretim testleri: unit+integration+smoke.

Anayasa özü: **denetlenmemiş üçüncü-taraf yetenek platforma SOKULAMAZ.** Placeholder/mock YOK; gerçek SQLite +
enjekte edilen deterministik installer üzerinden. Deterministik uyumluluk/allowlist, Madde 24 onay kapısı,
otomatik-red (güvenilmez), DÜRÜST no_connector, görünür install_failed, yaşam-döngüsü doğrulanır."""

import pytest

from mio_core.domains.marketplace import (
    ListingKind,
    ListingStatus,
    MarketplaceConfig,
    MarketplaceDomain,
    MarketplaceEvents,
    MarketplaceRepository,
    NotFoundError,
    TransitionError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(config=None):
    repo = MarketplaceRepository(":memory:")
    bus = EventBus(record=True)
    dom = MarketplaceDomain(repo, bus=bus, config=config)
    return dom, repo, bus


@pytest.fixture
def mk():
    return _build()


def _submit_trusted(d, actor="owner", **kw):
    name = kw.pop("name", "eklenti")
    base = dict(kind=ListingKind.PLUGIN, publisher="mio", signature="sig-abc", source_uri="")
    base.update(kw)
    return d.submit_listing(actor, name, **base)


# ---- UNIT: validation + authz + deterministik uyumluluk ----
def test_validation_authz_compat(mk):
    d, _r, _b = mk
    with pytest.raises(UnauthorizedError):
        d.submit_listing("Reasoning", "x")               # reader ama writer değil
    with pytest.raises(ValidationError):
        d.submit_listing("owner", "x", kind="uydurma")
    # güvenilir yayıncı + imza → uyumlu
    ok = _submit_trusted(d, name="iyi")
    assert ok["compatible"] is True and ok["compat_reasons"] == []
    # güvenilmez yayıncı + imzasız → uyumsuz (deterministik gerekçeler)
    bad = d.submit_listing("owner", "kotu", kind=ListingKind.PLUGIN, publisher="rando", signature="")
    assert bad["compatible"] is False
    assert "untrusted_source" in bad["compat_reasons"] and "unsigned" in bad["compat_reasons"]


# ---- INTEGRATION: güvenilmez listing ONAYLANAMAZ → otomatik reddedilir ----
def test_untrusted_auto_rejected_on_approve(mk):
    d, _r, bus = mk
    bad = d.submit_listing("owner", "kotu", kind=ListingKind.PLUGIN, publisher="rando", signature="")
    res = d.approve("owner", bad["id"])                  # approver olsa bile uyumsuz → reddedilir
    assert res["approved"] is False and res["status"] == ListingStatus.REJECTED
    assert "untrusted_source" in res["reasons"]
    assert any(e["type"] == MarketplaceEvents.LISTING_REJECTED for e in bus.history())
    # reddedilen kurulamaz (terminal)
    with pytest.raises(TransitionError):
        d.install("owner", bad["id"])


# ---- INTEGRATION: Madde 24 — yalnız approver onaylar ----
def test_only_approver_can_approve(mk):
    d, _r, _b = mk
    m = _submit_trusted(d, name="iyi")
    with pytest.raises(UnauthorizedError):
        d.approve("Engineering", m["id"])                # writer ama approver değil
    res = d.approve("owner", m["id"])                    # owner onaylar
    assert res["approved"] is True and res["status"] == ListingStatus.APPROVED


# ---- INTEGRATION: kurulum yalnız APPROVED + installer yoksa DÜRÜST no_connector ----
def test_install_requires_approved_and_no_connector(mk):
    d, _r, bus = mk
    m = _submit_trusted(d, name="iyi", kind=ListingKind.PLUGIN)
    # onaysız kurulamaz
    with pytest.raises(TransitionError):
        d.install("owner", m["id"])
    d.approve("owner", m["id"])
    # installer bağlı değil → dürüst no_connector, APPROVED kalır
    res = d.install("owner", m["id"])
    assert res["installed"] is False and res["reason"] == "no_connector"
    assert res["status"] == ListingStatus.APPROVED
    assert any(e["type"] == MarketplaceEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: installer ile kurulum + hata görünür ----
def test_install_success_and_failure_visible(mk):
    d, _r, bus = mk
    d.register_installer(ListingKind.PLUGIN, lambda ctx: {"install_ref": "ref-1"}, name="pkg-adapter")
    m = _submit_trusted(d, name="iyi", kind=ListingKind.PLUGIN)
    d.approve("owner", m["id"])
    ok = d.install("owner", m["id"])
    assert ok["installed"] is True and ok["status"] == ListingStatus.INSTALLED
    assert ok["listing"]["install_ref"] == "ref-1" and ok["listing"]["connector"] == "pkg-adapter"
    assert any(e["type"] == MarketplaceEvents.INSTALLED for e in bus.history())
    # kurulum hatası → görünür (Madde 27), APPROVED kalır
    d.register_installer(ListingKind.MODEL, lambda ctx: (_ for _ in ()).throw(RuntimeError("checksum")))
    m2 = d.submit_listing("owner", "model-x", kind=ListingKind.MODEL, publisher="mio", signature="s")
    d.approve("owner", m2["id"])
    fail = d.install("owner", m2["id"])
    assert fail["installed"] is False and fail["reason"] == "failed" and "checksum" in fail["error"]
    assert fail["status"] == ListingStatus.APPROVED
    assert any(e["type"] == MarketplaceEvents.INSTALL_FAILED for e in bus.history())


# ---- INTEGRATION: allowlist source_uri ile güven (config) ----
def test_trusted_via_source_allowlist():
    cfg = MarketplaceConfig()
    cfg.trusted_sources.add("partner.example.com")
    d, _r, _b = _build(config=cfg)
    m = d.submit_listing("owner", "ortak", kind=ListingKind.CAPABILITY, publisher="partner",
                         source_uri="https://partner.example.com/pkg", signature="s")
    assert m["compatible"] is True                       # publisher değil ama kaynak host allowlist'te
    res = d.approve("owner", m["id"])
    assert res["approved"] is True


# ---- INTEGRATION: remove + stats + contract ----
def test_remove_stats_contract(mk):
    d, _r, _b = mk
    d.register_installer(ListingKind.PLUGIN, lambda ctx: {"install_ref": "r"})
    m = _submit_trusted(d, name="iyi")
    d.approve("owner", m["id"]); d.install("owner", m["id"])
    rem = d.remove("owner", m["id"])
    assert rem["status"] == ListingStatus.REMOVED
    with pytest.raises(NotFoundError):
        d.get_listing("owner", "yok")
    s = d.stats()
    assert s["listings"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "marketplace" and "approve" in c["operations"]


# ---- SMOKE: boot() → deterministik red + Madde 24 uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    mkt = mio.marketplace_domain
    # güvenilmez üçüncü-taraf → onaylanamaz (otomatik red)
    bad = mkt.submit_listing("owner", "şüpheli", kind=ListingKind.PLUGIN, publisher="unknown", signature="")
    rej = mkt.approve("owner", bad["id"])
    assert rej["approved"] is False and rej["status"] == ListingStatus.REJECTED
    # güvenilir + onaylı ama installer yok → dürüst no_connector
    good = mkt.submit_listing("owner", "resmi", kind=ListingKind.PLUGIN, publisher="mio", signature="s")
    mkt.approve("owner", good["id"])
    inst = mkt.install("owner", good["id"])
    assert inst["installed"] is False and inst["reason"] == "no_connector"
    assert mkt.contract()["version"] == "1.0.0"
    mio.close()
