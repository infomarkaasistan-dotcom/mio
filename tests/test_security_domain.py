"""MIO Core · Security Domain (Faz 4 · Domain 15) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite principal + append-only audit üzerinden. Deterministik RBAC, kilitleme,
secret redaksiyonu (Anayasa), admin ayrımı, denetim izi, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.security import (
    Permission,
    Role,
    SecEvents,
    SecurityDomain,
    SecurityRepository,
    Severity,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    redact,
)
from mio_core.events import EventBus


def _build(config=None):
    repo = SecurityRepository(":memory:")
    bus = EventBus(record=True)
    dom = SecurityDomain(repo, bus=bus, config=config)
    return dom, repo, bus


@pytest.fixture
def sec():
    return _build()


# ---- UNIT: doğuştan kimlikler + RBAC ----
def test_born_with_principals_and_rbac(sec):
    d, _r, _b = sec
    assert d.check("owner", Permission.SECURITY_ADMIN)["allowed"] is True     # süper kullanıcı
    assert d.check("Finance", Permission.READ)["allowed"] is True             # brain rolü okur
    assert d.check("Finance", Permission.WRITE)["allowed"] is False           # brain yazamaz
    assert d.stats()["principals"] >= 5


# ---- UNIT: geçersiz izin + bilinmeyen principal ----
def test_invalid_permission_and_unknown(sec):
    d, _r, _b = sec
    with pytest.raises(ValidationError):
        d.check("owner", "uydurma-izin")
    r = d.check("hayalet", Permission.READ)
    assert r["allowed"] is False and r["reason"] == "bilinmeyen principal"


# ---- INTEGRATION: grant/revoke (admin) + authorization ----
def test_grant_revoke_and_admin(sec):
    d, _r, _b = sec
    assert d.check("Marketing", Permission.WRITE)["allowed"] is False
    d.grant("owner", "Marketing", Permission.WRITE)
    assert d.authorize("Marketing", Permission.WRITE) is True
    d.revoke("owner", "Marketing", Permission.WRITE)
    assert d.authorize("Marketing", Permission.WRITE) is False
    with pytest.raises(UnauthorizedError):
        d.grant("Marketing", "Sales", Permission.WRITE)          # admin değil
    with pytest.raises(NotFoundError):
        d.grant("owner", "yok-principal", Permission.READ)


# ---- INTEGRATION: kilitleme (ardışık başarısızlık) ----
def test_lockout_after_repeated_denials():
    from mio_core.domains.security import SecurityConfig
    d, _r, bus = _build(SecurityConfig(lockout_threshold=3))
    for _ in range(3):
        d.check("Sales", Permission.ADMIN)                       # Sales admin yok → başarısız
    r = d.check("Sales", Permission.READ)
    assert r["locked"] is True and r["allowed"] is False         # kilitli → okuma bile reddedilir
    assert any(e["type"] == SecEvents.LOCKED for e in bus.history())
    d.unlock("owner", "Sales")
    assert d.check("Sales", Permission.READ)["allowed"] is True  # açıldı → tekrar çalışır


def test_admin_lock_unlock(sec):
    d, _r, _b = sec
    d.lock("Security", "Marketing")                              # Security admin rolü
    assert d.check("Marketing", Permission.READ)["locked"] is True
    d.unlock("owner", "Marketing")
    assert d.check("Marketing", Permission.READ)["allowed"] is True


# ---- INTEGRATION: secret redaksiyonu (Anayasa: secret loglanmaz) ----
def test_secret_redaction():
    assert "***REDACTED***" in redact("api_key=sk-abcdef0123456789ABCDEF")
    assert "sk-" not in redact("token sk-abcdef0123456789ABCDEFxyz")
    d, repo, _b = _build()
    d.record_event("owner", "config_dump", "OPENAI_API_KEY=sk-verysecretkey0123456789ABCDEF",
                   severity=Severity.WARNING)
    trail = d.audit_trail("owner")
    assert trail and "sk-verysecret" not in trail[0]["detail"]   # denetime redakte yazıldı
    assert "***REDACTED***" in trail[0]["detail"]


# ---- INTEGRATION: assign_role + register + audit_trail admin ----
def test_register_assign_and_audit_admin(sec):
    d, _r, _b = sec
    d.register_principal("owner", "ExternalBot", roles=[Role.BRAIN])
    assert d.check("ExternalBot", Permission.READ)["allowed"] is True
    d.assign_role("owner", "ExternalBot", Role.OPERATIONS)
    assert d.check("ExternalBot", Permission.EXECUTE)["allowed"] is True
    with pytest.raises(UnauthorizedError):
        d.audit_trail("Marketing")                               # admin değil
    with pytest.raises(ValidationError):
        d.register_principal("owner", "X", roles=["uydurma-rol"])


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(sec):
    d, _r, _b = sec
    d.check("owner", Permission.READ)
    d.check("Finance", Permission.WRITE)                         # denial
    s = d.stats()
    assert s["checks"] >= 2 and s["denials"] >= 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "security" and "check" in c["operations"]


# ---- SMOKE: boot() → merkezî RBAC uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    assert mio.security.check("owner", Permission.ADMIN)["allowed"] is True
    assert mio.security.check("Communication", Permission.SECURITY_ADMIN)["allowed"] is False
    assert "***REDACTED***" in mio.security.redact("password: hunter2SuperSecretValue1234567890")
    assert mio.security.contract()["version"] == "1.0.0"
    mio.close()
