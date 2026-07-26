"""MIO Core · Customer Success Domain (Faz 3 · Domain 28) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite üzerinden. Deterministik health score/churn-risk, ticket/CSAT yaşam-
döngüsü, authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.customer_success import (
    CSEvents,
    CustomerRepository,
    CustomerSuccessDomain,
    Priority,
    TicketStatus,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = CustomerRepository(":memory:")
    bus = EventBus(record=True)
    dom = CustomerSuccessDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def cs():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(cs):
    d, _r, _b = cs
    with pytest.raises(ValidationError):
        d.add_account("owner", "  ")
    a = d.add_account("owner", "Acme")
    with pytest.raises(ValidationError):
        d.record_feedback("owner", a["id"], 9)             # CSAT 1-5 dışı
    with pytest.raises(UnauthorizedError):
        d.add_account("Reasoning", "X")                    # reader ama writer değil
    with pytest.raises(NotFoundError):
        d.open_ticket("owner", "yok", "konu")


# ---- INTEGRATION: deterministik health score ----
def test_health_score_deterministic(cs):
    d, _r, bus = cs
    a = d.add_account("owner", "Sağlıklı")
    d.record_feedback("owner", a["id"], 5)                 # +20 → 100 (clamp)
    h = d.health("owner", a["id"])
    assert h["health_score"] == 100.0 and h["churn_risk"] is False   # 120 → [0,100] kırpıldı
    assert d.health("owner", a["id"]) == h                # determinizm
    # nötr CSAT'li ayrı hesapta ticket etkisi net görülür (kırpma maskelemez)
    b = d.add_account("owner", "Nötr")
    d.record_feedback("owner", b["id"], 3)                 # +0
    d.open_ticket("owner", b["id"], "kritik hata", priority=Priority.HIGH)   # -15
    h2 = d.health("owner", b["id"])
    assert h2["health_score"] == 85.0 and h2["open_tickets"] == 1


def test_churn_risk_flag(cs):
    d, _r, bus = cs
    a = d.add_account("owner", "Riskli")
    d.record_feedback("owner", a["id"], 1)                 # -20
    for _ in range(3):
        d.open_ticket("owner", a["id"], "sorun", priority=Priority.HIGH)   # -45
    h = d.health("owner", a["id"])                         # 100-45-20 = 35 < 50
    assert h["health_score"] == 35.0 and h["churn_risk"] is True
    assert any(e["type"] == CSEvents.CHURN_RISK for e in bus.history())


def test_resolved_ticket_restores_health(cs):
    d, _r, _b = cs
    a = d.add_account("owner", "X")
    t = d.open_ticket("owner", a["id"], "sorun", priority=Priority.MEDIUM)  # -7
    assert d.health("owner", a["id"])["health_score"] == 93.0
    d.update_ticket("owner", t["id"], TicketStatus.RESOLVED)               # çözüldü → health etkilemez
    assert d.health("owner", a["id"])["health_score"] == 100.0
    with pytest.raises(NotFoundError):
        d.update_ticket("owner", "yok", TicketStatus.RESOLVED)


# ---- INTEGRATION: no-csat honest + stats + contract ----
def test_no_csat_and_stats_contract(cs):
    d, _r, _b = cs
    a = d.add_account("owner", "Yeni")
    h = d.health("owner", a["id"])
    assert h["avg_csat"] is None and h["health_score"] == 100.0   # CSAT yok → nötr
    s = d.stats()
    assert s["accounts"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "customer_success" and "health" in c["operations"]


# ---- SMOKE: boot() → uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    a = mio.customer_success.add_account("owner", "Müşteri X", tier="premium")
    mio.customer_success.open_ticket("owner", a["id"], "yavaşlık", priority=Priority.HIGH)
    mio.customer_success.record_feedback("owner", a["id"], 2)
    h = mio.customer_success.health("owner", a["id"])
    assert h["health_score"] == 100.0 - 15 - 10                   # -15 ticket, -10 csat(2)
    assert mio.customer_success.contract()["version"] == "1.0.0"
    mio.close()
