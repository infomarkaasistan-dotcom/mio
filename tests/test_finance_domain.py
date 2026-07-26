"""MIO Core · Finance Operations Domain (Faz 3 · Domain 25) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite defter üzerinden. Deterministik nakit akışı/runway, Financial Rule
(onaysız yükümlülük yürürlüğe girmez), authorization/approver ayrımı, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.finance import (
    CommitmentStatus,
    FinanceDomain,
    FinanceEvents,
    FinanceRepository,
    FinancialRuleError,
    NotFoundError,
    TxnKind,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = FinanceRepository(":memory:")
    bus = EventBus(record=True)
    dom = FinanceDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def fin():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(fin):
    d, _r, _b = fin
    with pytest.raises(ValidationError):
        d.record_transaction("owner", "uydurma", 100)
    with pytest.raises(ValidationError):
        d.record_transaction("owner", TxnKind.INCOME, -5)     # pozitif olmalı
    with pytest.raises(UnauthorizedError):
        d.record_transaction("Reasoning", TxnKind.INCOME, 10)  # reader ama writer değil


# ---- INTEGRATION: nakit akışı + kategori + runway (deterministik) ----
def test_cash_flow_and_runway(fin):
    d, _r, _b = fin
    d.record_transaction("owner", TxnKind.INCOME, 1000, category="satış")
    d.record_transaction("owner", TxnKind.EXPENSE, 300, category="reklam")
    d.record_transaction("owner", TxnKind.EXPENSE, 100, category="reklam")
    cf = d.cash_flow("owner")
    assert cf["income"] == 1000 and cf["expense"] == 400 and cf["net"] == 600
    cats = d.category_breakdown("owner")["categories"]
    assert cats["reklam"]["expense"] == 400 and cats["satış"]["income"] == 1000
    rw = d.runway("owner", months=1.0)
    assert rw["monthly_burn"] == 400 and rw["runway_months"] == 1.5   # 600/400
    assert d.runway("owner", months=1.0) == rw                        # determinizm


def test_runway_no_burn_honest(fin):
    d, _r, _b = fin
    d.record_transaction("owner", TxnKind.INCOME, 500)
    assert d.runway("owner")["runway_months"] is None                # gider yok → uydurma yok


# ---- INTEGRATION: Financial Rule (Madde 4) ----
def test_financial_rule_commitment_flow(fin):
    d, _r, bus = fin
    c = d.record_commitment("Finance", "sunucu kirası", 500)
    assert c["status"] == CommitmentStatus.PENDING                    # onaysız yürürlüğe girmez
    with pytest.raises(UnauthorizedError):
        d.approve_commitment("Finance", c["id"])                     # Finance approver DEĞİL (Madde 4)
    approved = d.approve_commitment("owner", c["id"])                # owner onaylar
    assert approved["status"] == CommitmentStatus.EXECUTED and approved["approved_by"] == "owner"
    # onaylanan yükümlülük gidere döndü
    assert d.cash_flow("owner")["expense"] == 500
    with pytest.raises(FinancialRuleError):
        d.approve_commitment("owner", c["id"])                       # zaten executed → tekrar onaylanamaz
    assert any(e["type"] == FinanceEvents.COMMITMENT_APPROVED for e in bus.history())


def test_reject_commitment(fin):
    d, _r, _b = fin
    c = d.record_commitment("owner", "gereksiz harcama", 200)
    r = d.reject_commitment("Executive", c["id"])
    assert r["status"] == CommitmentStatus.REJECTED
    assert d.cash_flow("owner")["expense"] == 0                       # reddedilen → gider yok
    with pytest.raises(NotFoundError):
        d.approve_commitment("owner", "yok-id")


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(fin):
    d, _r, _b = fin
    d.record_transaction("owner", TxnKind.INCOME, 100)
    d.record_commitment("owner", "x", 50)
    s = d.stats()
    assert s["transactions"] == 1 and s["pending_commitments"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "finance" and "approve_commitment" in c["operations"]


# ---- SMOKE: boot() → Financial Rule uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    mio.finance.record_transaction("owner", TxnKind.INCOME, 5000, category="gelir")
    com = mio.finance.record_commitment("Finance", "reklam bütçesi", 1000)
    assert com["status"] == CommitmentStatus.PENDING                 # onaysız beklemede (Madde 4)
    mio.finance.approve_commitment("owner", com["id"])
    assert mio.finance.cash_flow("owner")["balance"] == 4000
    assert mio.finance.contract()["version"] == "1.0.0"
    mio.close()
