"""MIO Core · Sales & CRM Domain (Faz 3 · Domain 26) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite üzerinden. Deterministik pipeline metrikleri (ağırlıklı değer/win rate),
lead qualification, authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.sales import (
    ContactKind,
    SalesCRMDomain,
    SalesEvents,
    SalesRepository,
    Stage,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = SalesRepository(":memory:")
    bus = EventBus(record=True)
    dom = SalesCRMDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def sc():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(sc):
    d, _r, _b = sc
    with pytest.raises(ValidationError):
        d.add_contact("owner", "  ")
    with pytest.raises(ValidationError):
        d.add_contact("owner", "X", kind="uydurma")
    with pytest.raises(UnauthorizedError):
        d.add_contact("Reasoning", "X")                    # reader ama writer değil
    with pytest.raises(NotFoundError):
        d.add_opportunity("owner", "yok-contact", "F", 100)


# ---- INTEGRATION: pipeline metrikleri (deterministik ağırlık) ----
def test_pipeline_weighted_and_winrate(sc):
    d, _r, bus = sc
    c = d.add_contact("owner", "Acme", kind=ContactKind.LEAD)
    d.add_opportunity("owner", c["id"], "Proje A", 1000, stage=Stage.PROPOSAL)     # 0.5 → 500
    d.add_opportunity("owner", c["id"], "Proje B", 2000, stage=Stage.NEGOTIATION)  # 0.7 → 1400
    d.add_opportunity("owner", c["id"], "Proje C", 500, stage=Stage.WON)
    d.add_opportunity("owner", c["id"], "Proje D", 300, stage=Stage.LOST)
    p = d.pipeline("owner")
    assert p["open_value"] == 3000 and p["weighted_value"] == 1900   # 500 + 1400
    assert p["won"] == 1 and p["lost"] == 1 and p["win_rate"] == 0.5
    assert p["by_stage"][Stage.PROPOSAL] == 1
    assert d.pipeline("owner") == p                                  # determinizm
    assert any(e["type"] == SalesEvents.OPPORTUNITY_ADDED for e in bus.history())


def test_advance_stage(sc):
    d, _r, bus = sc
    c = d.add_contact("owner", "X")
    o = d.add_opportunity("owner", c["id"], "F", 100, stage=Stage.LEAD)
    upd = d.advance_stage("owner", o["id"], Stage.QUALIFIED)
    assert upd["stage"] == Stage.QUALIFIED and upd["weighted_value"] == 30.0   # 100*0.3
    with pytest.raises(NotFoundError):
        d.advance_stage("owner", "yok", Stage.WON)
    with pytest.raises(ValidationError):
        d.advance_stage("owner", o["id"], "uydurma")
    assert any(e["type"] == SalesEvents.STAGE_CHANGED for e in bus.history())


# ---- INTEGRATION: lead qualification (öneri, karar değil) ----
def test_qualify(sc):
    d, _r, _b = sc
    q = d.qualify("Sales", context_tags=["cold_lead"])
    assert any("değer-önce" in r.lower() for r in q["recommendations"])
    assert q["decision_authority"] == "Executive"
    assert d.qualify("owner", context_tags=[])["recommendations"]   # sinyal yoksa da öneri döner


# ---- INTEGRATION: list + stats + contract ----
def test_list_stats_contract(sc):
    d, _r, _b = sc
    c = d.add_contact("owner", "X", kind=ContactKind.CUSTOMER)
    d.add_opportunity("owner", c["id"], "F", 100)
    assert len(d.list_contacts("owner", kind=ContactKind.CUSTOMER)) == 1
    assert len(d.list_opportunities("owner", stage=Stage.LEAD)) == 1
    s = d.stats()
    assert s["contacts"] == 1 and s["opportunities"] == 1 and s["contract_version"] == "1.0.0"
    c2 = d.contract()
    assert c2["domain"] == "sales" and "pipeline" in c2["operations"]


# ---- SMOKE: boot() → uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    c = mio.sales.add_contact("owner", "Müşteri A", kind=ContactKind.LEAD)
    mio.sales.add_opportunity("owner", c["id"], "Anlaşma", 5000, stage=Stage.NEGOTIATION)
    p = mio.sales.pipeline("owner")
    assert p["weighted_value"] == 3500.0                            # 5000*0.7
    assert mio.sales.qualify("owner", context_tags=["cold_lead"])["decision_authority"] == "Executive"
    assert mio.sales.contract()["version"] == "1.0.0"
    mio.close()
