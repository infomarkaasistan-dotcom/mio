"""MIO Core · Knowledge Marketplace Domain (Faz 5 · Domain 38) — üretim testleri: unit+integration+smoke.

Anayasa özü: **denetlenmemiş bilgi Knowledge Domain'e/çekirdeğe SOKULAMAZ.** Placeholder/mock YOK; gerçek SQLite
+ enjekte edilen deterministik source üzerinden. Deterministik lisans/allowlist, Madde 24 onay/otomatik-red,
provenance etiketi, DÜRÜST no_connector, görünür import_failed, yaşam-döngüsü doğrulanır."""

import pytest

from mio_core.domains.knowledge_marketplace import (
    KnowledgeMarketConfig,
    KnowledgeMarketEvents,
    KnowledgeMarketRepository,
    KnowledgeMarketplaceDomain,
    NotFoundError,
    PackKind,
    PackStatus,
    TransitionError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(config=None):
    repo = KnowledgeMarketRepository(":memory:")
    bus = EventBus(record=True)
    dom = KnowledgeMarketplaceDomain(repo, bus=bus, config=config)
    return dom, repo, bus


@pytest.fixture
def km():
    return _build()


def _submit_ok(d, actor="owner", **kw):
    name = kw.pop("name", "gerçekler")
    base = dict(kind=PackKind.FACT_SET, publisher="mio", license="CC-BY", checksum="sha256:abc")
    base.update(kw)
    return d.submit_pack(actor, name, **base)


# ---- UNIT: validation + authz + deterministik uyumluluk ----
def test_validation_authz_compat(km):
    d, _r, _b = km
    with pytest.raises(UnauthorizedError):
        d.submit_pack("Reasoning", "x")                  # reader ama writer değil
    with pytest.raises(ValidationError):
        d.submit_pack("owner", "x", kind="uydurma")
    ok = _submit_ok(d, name="iyi")
    assert ok["compatible"] is True and ok["compat_reasons"] == []
    # güvenilmez + lisanssız + checksum'suz → çok gerekçeli uyumsuz
    bad = d.submit_pack("owner", "kotu", kind=PackKind.FACT_SET, publisher="rando", license="", checksum="")
    assert bad["compatible"] is False
    for r in ("untrusted_source", "license_not_allowed", "missing_checksum"):
        assert r in bad["compat_reasons"]


# ---- INTEGRATION: lisanssız/denetimsiz onaylanamaz → otomatik red ----
def test_untrusted_auto_rejected(km):
    d, _r, bus = km
    bad = d.submit_pack("owner", "kotu", kind=PackKind.ONTOLOGY, publisher="rando", license="WTFPL",
                        checksum="c")
    res = d.approve("owner", bad["id"])
    assert res["approved"] is False and res["status"] == PackStatus.REJECTED
    assert "untrusted_source" in res["reasons"] and "license_not_allowed" in res["reasons"]
    assert any(e["type"] == KnowledgeMarketEvents.PACK_REJECTED for e in bus.history())
    with pytest.raises(TransitionError):
        d.import_pack("owner", bad["id"])                # reddedilen import edilemez


# ---- INTEGRATION: Madde 24 — yalnız approver onaylar ----
def test_only_approver_approves(km):
    d, _r, _b = km
    p = _submit_ok(d, name="iyi")
    with pytest.raises(UnauthorizedError):
        d.approve("Knowledge", p["id"])                  # writer ama approver değil
    res = d.approve("owner", p["id"])
    assert res["approved"] is True and res["status"] == PackStatus.APPROVED


# ---- INTEGRATION: import yalnız APPROVED + source yoksa DÜRÜST no_connector ----
def test_import_requires_approved_and_no_connector(km):
    d, _r, bus = km
    p = _submit_ok(d, name="iyi")
    with pytest.raises(TransitionError):
        d.import_pack("owner", p["id"])                  # onaysız import edilemez
    d.approve("owner", p["id"])
    res = d.import_pack("owner", p["id"])                # source bağlı değil → dürüst no_connector
    assert res["imported"] is False and res["reason"] == "no_connector"
    assert res["status"] == PackStatus.APPROVED
    assert any(e["type"] == KnowledgeMarketEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: source ile import + provenance etiketi + hata görünür ----
def test_import_success_provenance_and_failure(km):
    d, _r, bus = km
    d.register_source(PackKind.FACT_SET, lambda ctx: {"imported_ref": "kb-1", "imported_items": 42},
                      name="kb-adapter")
    p = _submit_ok(d, name="iyi", publisher="mio", license="MIT", checksum="sha256:z")
    d.approve("owner", p["id"])
    ok = d.import_pack("owner", p["id"])
    assert ok["imported"] is True and ok["status"] == PackStatus.IMPORTED
    assert ok["pack"]["imported_items"] == 42 and ok["pack"]["connector"] == "kb-adapter"
    # provenance (izlenebilirlik) etiketi doğru
    prov = ok["pack"]["provenance"]
    assert prov["publisher"] == "mio" and prov["license"] == "MIT" and prov["approved_by"] == "owner"
    assert prov["checksum"] == "sha256:z" and "imported_at" in prov
    assert any(e["type"] == KnowledgeMarketEvents.IMPORTED for e in bus.history())
    # import hatası → görünür (Madde 27), APPROVED kalır
    d.register_source(PackKind.SKILL, lambda ctx: (_ for _ in ()).throw(RuntimeError("şema hatası")))
    s = d.submit_pack("owner", "beceri", kind=PackKind.SKILL, publisher="mio", license="MIT", checksum="c")
    d.approve("owner", s["id"])
    fail = d.import_pack("owner", s["id"])
    assert fail["imported"] is False and fail["reason"] == "failed" and "şema hatası" in fail["error"]
    assert fail["status"] == PackStatus.APPROVED
    assert any(e["type"] == KnowledgeMarketEvents.IMPORT_FAILED for e in bus.history())


# ---- INTEGRATION: kaynak allowlist ile güven (config) ----
def test_trusted_via_source_allowlist():
    cfg = KnowledgeMarketConfig()
    cfg.trusted_sources.add("data.partner.org")
    d, _r, _b = _build(config=cfg)
    p = d.submit_pack("owner", "ortak-veri", kind=PackKind.FACT_SET, publisher="partner",
                      source_uri="https://data.partner.org/pack", license="CC0", checksum="c")
    assert p["compatible"] is True                       # publisher değil ama kaynak host allowlist'te
    assert d.approve("owner", p["id"])["approved"] is True


# ---- INTEGRATION: remove + stats + contract ----
def test_remove_stats_contract(km):
    d, _r, _b = km
    d.register_source(PackKind.FACT_SET, lambda ctx: {"imported_ref": "r", "imported_items": 1})
    p = _submit_ok(d, name="iyi")
    d.approve("owner", p["id"]); d.import_pack("owner", p["id"])
    rem = d.remove("owner", p["id"])
    assert rem["status"] == PackStatus.REMOVED
    with pytest.raises(NotFoundError):
        d.get_pack("owner", "yok")
    s = d.stats()
    assert s["packs"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "knowledge_marketplace" and "import_pack" in c["operations"]


# ---- SMOKE: boot() → deterministik red + Madde 24 + provenance uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    kmt = mio.knowledge_marketplace
    # lisanssız üçüncü-taraf bilgi → onaylanamaz (otomatik red)
    bad = kmt.submit_pack("owner", "şüpheli", kind=PackKind.FACT_SET, publisher="unknown", license="",
                          checksum="")
    rej = kmt.approve("owner", bad["id"])
    assert rej["approved"] is False and rej["status"] == PackStatus.REJECTED
    # güvenilir + onaylı ama source yok → dürüst no_connector
    good = kmt.submit_pack("owner", "resmi", kind=PackKind.FACT_SET, publisher="mio", license="CC-BY",
                           checksum="sha256:x")
    kmt.approve("owner", good["id"])
    res = kmt.import_pack("owner", good["id"])
    assert res["imported"] is False and res["reason"] == "no_connector"
    assert kmt.contract()["version"] == "1.0.0"
    mio.close()
