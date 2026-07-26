"""MIO Core · Audit & Compliance Domain (Faz 2 · Domain 18) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite append-only ledger + compliance kaydı üzerinden. Değişmez audit,
uyum değerlendirmesi (§10), 'en kötü' genel seviye determinizmi, istisna kaydı, authorization, events ve
uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.audit import (
    AuditComplianceDomain,
    AuditEvents,
    AuditRepository,
    ComplianceLevel,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = AuditRepository(":memory:")
    bus = EventBus(record=True)
    dom = AuditComplianceDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def ac():
    return _build()


# ---- UNIT: log validation + authorization ----
def test_log_validation_and_authz(ac):
    d, _r, _b = ac
    with pytest.raises(ValidationError):
        d.log("owner", "  ")
    with pytest.raises(ValidationError):
        d.log("owner", "act", outcome="uydurma")
    with pytest.raises(UnauthorizedError):
        d.log("yabanci", "act")                            # yetkisiz aktör
    assert d.log("Planning", "plan.executed", outcome="success")["action"] == "plan.executed"


# ---- INTEGRATION: append-only audit + trail filtreleri ----
def test_audit_ledger_and_trail(ac):
    d, _r, bus = ac
    d.log("Executive", "decision.made", resource="dec:1", outcome="success")
    d.log("Execution", "tool.run", resource="cap:x", outcome="failure")
    d.log("Security", "access.check", outcome="denied")
    assert len(d.trail("owner")) == 3
    assert d.trail("owner", outcome="failure")[0]["action"] == "tool.run"
    assert d.trail("Security", target_actor="Executive")[0]["actor"] == "Executive"
    with pytest.raises(UnauthorizedError):
        d.trail("yabanci")                                 # okuma yetkisi yok
    assert any(e["type"] == AuditEvents.LOGGED for e in bus.history())


# ---- INTEGRATION: compliance değerlendirmesi + 'en kötü' genel seviye ----
def test_compliance_report_worst_wins(ac):
    d, _r, bus = ac
    d.assess("owner", "platform", "Madde 3", ComplianceLevel.FULLY)
    d.assess("owner", "platform", "Madde 27", ComplianceLevel.SUBSTANTIALLY)
    d.assess("Security", "platform", "Madde 28", ComplianceLevel.PARTIALLY)
    rep = d.compliance_report("owner")
    assert rep["overall"] == ComplianceLevel.PARTIALLY     # en kötü kazanır
    assert rep["assessments"] == 3 and rep["by_level"][ComplianceLevel.FULLY] == 1
    assert any(e["type"] == AuditEvents.COMPLIANCE_ASSESSED for e in bus.history())
    # değerlendirmenin kendisi de audit'lendi (izlenebilirlik)
    assert any(r["action"] == "compliance.assess" for r in d.trail("owner"))


def test_assess_validation_and_admin(ac):
    d, _r, _b = ac
    with pytest.raises(ValidationError):
        d.assess("owner", "platform", "Madde 1", "süper-uyumlu")   # geçersiz seviye
    with pytest.raises(UnauthorizedError):
        d.assess("Operations", "platform", "Madde 1", ComplianceLevel.FULLY)  # admin değil


# ---- INTEGRATION: istisna (EXCEPTION APPROVED) ----
def test_register_exception(ac):
    d, _r, bus = ac
    with pytest.raises(ValidationError):
        d.register_exception("owner", "platform", "Madde 10", "")   # gerekçe zorunlu
    out = d.register_exception("owner", "platform", "Madde 10", "Multi-org ertelendi",
                               planned_phase="Production Hardening")
    assert out["level"] == ComplianceLevel.EXCEPTION and out["planned_phase"] == "Production Hardening"
    assert d.compliance_report("owner")["overall"] == ComplianceLevel.EXCEPTION
    assert any(e["type"] == AuditEvents.EXCEPTION_REGISTERED for e in bus.history())


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(ac):
    d, _r, _b = ac
    d.log("owner", "x", outcome="failure")
    d.log("owner", "y", outcome="denied")
    d.assess("owner", "platform", "Madde 3", ComplianceLevel.FULLY)
    s = d.stats()
    assert s["audit_entries"] >= 3 and s["failures"] >= 1 and s["denied"] >= 1
    assert s["compliance_records"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "audit_compliance" and "compliance_report" in c["operations"]


# ---- SMOKE: boot() → uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    mio.audit.log("owner", "system.boot", resource="mio", outcome="success")
    mio.audit.assess("owner", "platform", "Madde 28", ComplianceLevel.PARTIALLY,
                     note="resilience mekanizması var, yük kanıtı yok")
    rep = mio.audit.compliance_report("owner")
    assert rep["overall"] == ComplianceLevel.PARTIALLY
    assert mio.audit.trail("owner")[0] is not None
    assert mio.audit.contract()["version"] == "1.0.0"
    mio.close()
