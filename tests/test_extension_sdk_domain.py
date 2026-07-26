"""MIO Core · Extension SDK Domain (Faz 5 · Domain 43, SON ana domain) — üretim testleri: unit+integration+smoke.

Anayasa özü: **denetlenmemiş/aşırı-izinli üçüncü-taraf uzantı platforma SOKULAMAZ; etkinleştirme ONAY ister
(Madde 24).** Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik host sandbox üzerinden.
Deterministik manifest/izin doğrulama, en-az-yetki, otomatik-red, Madde 24 etkinleştirme, DÜRÜST no_connector,
yaşam-döngüsü doğrulanır."""

import pytest

from mio_core.domains.extension_sdk import (
    ExtKind,
    ExtStatus,
    ExtensionConfig,
    ExtensionEvents,
    ExtensionRepository,
    ExtensionSDKDomain,
    NotFoundError,
    TransitionError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(config=None):
    repo = ExtensionRepository(":memory:")
    bus = EventBus(record=True)
    dom = ExtensionSDKDomain(repo, bus=bus, config=config)
    return dom, repo, bus


@pytest.fixture
def ex():
    return _build()


def _reg_ok(d, actor="owner", **kw):
    name = kw.pop("name", "araç")
    base = dict(kind=ExtKind.TOOL, publisher="mio", signature="sig", requested_permissions=["read:knowledge"])
    base.update(kw)
    return d.register_extension(actor, name, **base)


# ---- UNIT: validation + authz + deterministik izin değerlendirme ----
def test_validation_authz_permissions(ex):
    d, _r, _b = ex
    with pytest.raises(UnauthorizedError):
        d.register_extension("Reasoning", "x")                # reader ama writer değil
    with pytest.raises(ValidationError):
        d.register_extension("owner", "x", kind="uydurma")
    ok = _reg_ok(d, name="iyi")
    assert ok["valid"] is True and ok["validation_reasons"] == []
    # aşırı-izinli + güvenilmez + imzasız → çok gerekçeli geçersiz
    bad = d.register_extension("owner", "kotu", kind=ExtKind.TOOL, publisher="rando", signature="",
                               requested_permissions=["read:knowledge", "write:everything"])
    assert bad["valid"] is False
    assert "untrusted_publisher" in bad["validation_reasons"] and "unsigned" in bad["validation_reasons"]
    assert "permission_not_allowed:write:everything" in bad["validation_reasons"]


# ---- INTEGRATION: aşırı-izinli/denetimsiz doğrulanamaz → otomatik red ----
def test_untrusted_auto_rejected(ex):
    d, _r, bus = ex
    bad = d.register_extension("owner", "kotu", kind=ExtKind.HOOK, publisher="rando", signature="",
                               requested_permissions=["read:knowledge"])
    res = d.validate("owner", bad["id"])
    assert res["validated"] is False and res["status"] == ExtStatus.REJECTED
    assert "untrusted_publisher" in res["reasons"]
    assert any(e["type"] == ExtensionEvents.REJECTED for e in bus.history())
    with pytest.raises(TransitionError):
        d.enable("owner", bad["id"])                          # reddedilen etkinleştirilemez


# ---- INTEGRATION: Madde 24 — yalnız approver etkinleştirir + en-az-yetki ----
def test_enable_requires_approver_and_least_privilege(ex):
    d, _r, bus = ex
    ext = _reg_ok(d, name="iyi", requested_permissions=["read:knowledge", "read:metrics"])
    d.validate("owner", ext["id"])
    with pytest.raises(UnauthorizedError):
        d.enable("Engineering", ext["id"])                    # writer ama approver değil
    res = d.enable("owner", ext["id"])
    assert res["enabled"] is True and res["status"] == ExtStatus.ENABLED
    # en-az-yetki: yalnız istenen + izinli izinler verildi
    assert set(res["extension"]["granted_permissions"]) == {"read:knowledge", "read:metrics"}
    assert res["extension"]["approved_by"] == "owner"
    assert any(e["type"] == ExtensionEvents.ENABLED for e in bus.history())


# ---- INTEGRATION: enable yalnız VALIDATED; invoke yalnız ENABLED + host yoksa no_connector ----
def test_lifecycle_and_no_connector(ex):
    d, _r, bus = ex
    ext = _reg_ok(d, name="iyi", kind=ExtKind.TOOL)
    with pytest.raises(TransitionError):
        d.enable("owner", ext["id"])                          # henüz validated değil
    d.validate("owner", ext["id"])
    d.enable("owner", ext["id"])
    # host sandbox yok → dürüst no_connector
    res = d.invoke("owner", ext["id"], {"q": 1})
    assert res["invoked"] is False and res["reason"] == "no_connector"
    assert any(e["type"] == ExtensionEvents.NO_CONNECTOR for e in bus.history())
    # disable → izinler geri alınır, artık çağrılamaz
    d.disable("owner", ext["id"])
    assert d.get_extension("owner", ext["id"])["granted_permissions"] == []
    with pytest.raises(TransitionError):
        d.invoke("owner", ext["id"])


# ---- INTEGRATION: host sandbox ile çağrı + hata görünür ----
def test_invoke_via_host_and_failure(ex):
    d, _r, bus = ex
    d.register_host(ExtKind.TOOL, lambda ctx: {"echo": ctx["payload"].get("q")}, name="wasm-sandbox")
    ext = _reg_ok(d, name="iyi", kind=ExtKind.TOOL)
    d.validate("owner", ext["id"]); d.enable("owner", ext["id"])
    ok = d.invoke("owner", ext["id"], {"q": 42})
    assert ok["invoked"] is True and ok["result"] == {"echo": 42} and ok["connector"] == "wasm-sandbox"
    assert any(e["type"] == ExtensionEvents.INVOKED for e in bus.history())
    # uzantı hatası → görünür (failed), sistemi bozmaz
    d.register_host(ExtKind.HOOK, lambda ctx: (_ for _ in ()).throw(RuntimeError("sandbox ihlali")))
    h = d.register_extension("owner", "kanca", kind=ExtKind.HOOK, publisher="mio", signature="s",
                             requested_permissions=["read:metrics"])
    d.validate("owner", h["id"]); d.enable("owner", h["id"])
    fail = d.invoke("owner", h["id"])
    assert fail["invoked"] is False and fail["reason"] == "failed" and "sandbox ihlali" in fail["error"]


# ---- INTEGRATION: özel izin allowlist (config) ----
def test_custom_permission_allowlist():
    cfg = ExtensionConfig()
    cfg.allowed_permissions.add("write:memory")
    d, _r, _b = _build(config=cfg)
    ext = d.register_extension("owner", "yazıcı", kind=ExtKind.WORKFLOW, publisher="mio", signature="s",
                               requested_permissions=["write:memory"])
    assert ext["valid"] is True                              # artık allowlist'te
    d.validate("owner", ext["id"])
    assert d.enable("owner", ext["id"])["enabled"] is True


# ---- INTEGRATION: hosts + permissions_catalog + stats + contract ----
def test_hosts_catalog_stats_contract(ex):
    d, _r, _b = ex
    _reg_ok(d, name="a")
    s = d.stats()
    assert s["extensions"] == 1 and s["contract_version"] == "1.0.0"
    assert "read:knowledge" in d.permissions_catalog("owner")["grantable"]
    assert ExtKind.TOOL in d.hosts("owner")["all_kinds"]
    c = d.contract()
    assert c["domain"] == "extension_sdk" and "enable" in c["operations"]
    with pytest.raises(NotFoundError):
        d.get_extension("owner", "yok")


# ---- SMOKE: boot() → deterministik red + Madde 24 + no_connector uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    sdk = mio.extension_sdk
    # aşırı-izinli üçüncü-taraf → doğrulanamaz (otomatik red)
    bad = sdk.register_extension("owner", "şüpheli", kind=ExtKind.TOOL, publisher="unknown", signature="",
                                 requested_permissions=["root:all"])
    rej = sdk.validate("owner", bad["id"])
    assert rej["validated"] is False and rej["status"] == ExtStatus.REJECTED
    # güvenilir + doğrulanmış + onaylı ama host yok → dürüst no_connector
    good = sdk.register_extension("owner", "resmi", kind=ExtKind.TOOL, publisher="mio", signature="s",
                                  requested_permissions=["read:knowledge"])
    sdk.validate("owner", good["id"])
    sdk.enable("owner", good["id"])
    inv = sdk.invoke("owner", good["id"])
    assert inv["invoked"] is False and inv["reason"] == "no_connector"
    assert sdk.contract()["version"] == "1.0.0"
    mio.close()
