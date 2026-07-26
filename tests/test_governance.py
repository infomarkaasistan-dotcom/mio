"""MIO Core · E4 Decision & Governance — üretim testleri (deterministik, LLM-siz)."""

import pytest

from mio_core.executive import (
    DecisionRequest,
    DecisionStatus,
    ExecutiveState,
    GovernanceEngine,
    SQLiteExecutiveStateStore,
    Verdict,
)
from mio_core.executive.governance import EXTERNAL, IRREVERSIBLE, REVERSIBLE


@pytest.fixture
def state(tmp_path):
    s = SQLiteExecutiveStateStore(str(tmp_path / "e4.db"))
    st = ExecutiveState(s)
    st.ensure_identity("MIO")
    st.set_mission("uzun vadeli hedef yönetimi")
    st.track_goal("g1", horizon_days=90)
    st.set_strategy("g1", "içerik üret")
    yield st
    s.close()


@pytest.fixture
def gov(state):
    return GovernanceEngine(state)


def _req(**kw) -> DecisionRequest:
    base = dict(kind="start_plan", chosen="bir iş", goal_id="g1",
                reversibility=REVERSIBLE, evidence_refs=["mem:1"])
    base.update(kw)
    return DecisionRequest(**base)


# ---- APPROVE ----
def test_approve_aligned_reversible_with_evidence(gov, state):
    res = gov.decide(_req(chosen="landing page", expectation="+ziyaretçi"))
    assert res.verdict is Verdict.APPROVE
    assert res.decision_id is not None
    rec = state.recent_decisions()[0]
    assert rec.id == res.decision_id
    assert rec.status is DecisionStatus.COMMITTED
    assert rec.chosen == "landing page" and rec.expectation == "+ziyaretçi"
    assert rec.evidence_refs == ["mem:1"]
    assert set(rec.score) >= {"risk", "confidence", "priority", "composite"}


# ---- REJECT ----
def test_reject_misaligned_goal(gov, state):
    res = gov.decide(_req(goal_id="gX"))          # gX aktif değil
    assert res.verdict is Verdict.REJECT
    assert any(v.rule == "alignment" and v.severity == "hard" for v in res.violations)
    assert state.recent_decisions()[0].status is DecisionStatus.REJECTED
    assert state.recent_decisions()[0].chosen.startswith("reddedildi:")


def test_reject_capability_not_connected(state):
    gov = GovernanceEngine(state, is_capability_available=lambda c: c != "ses")
    res = gov.decide(_req(required_capabilities=["ses"]))
    assert res.verdict is Verdict.REJECT
    assert any(v.rule == "capability" for v in res.violations)


# ---- DEFER ----
def test_defer_when_needs_evidence(gov, state):
    res = gov.decide(_req(needs_evidence=True, needed_evidence=["pazar boyutu", "rakip fiyatı"]))
    assert res.verdict is Verdict.DEFER
    rec = state.get_decision(res.decision_id)
    assert rec.status is DecisionStatus.DEFERRED and rec.chosen == "bir iş"  # orijinal eylem korunur
    assert rec.score["needed_evidence"] == ["pazar boyutu", "rakip fiyatı"]
    assert rec.score["composite"] is not None          # tam skor da taşınıyor
    assert [d.id for d in state.deferred_decisions()] == [res.decision_id]


def test_defer_when_no_basis(gov):
    # hedef yok + kanıt yok → güven tabanı düşük → yeterli temel yok → DEFER
    res = gov.decide(DecisionRequest(kind="explore", chosen="belirsiz iş",
                                     goal_id=None, reversibility=REVERSIBLE, evidence_refs=[]))
    assert res.verdict is Verdict.DEFER


# ---- AWAIT_APPROVAL / ESCALATE (sonuçlu aksiyonlar) ----
def test_await_approval_external_confident(gov, state):
    res = gov.decide(_req(reversibility=EXTERNAL, evidence_refs=["mem:1"]))
    assert res.verdict is Verdict.AWAIT_APPROVAL
    assert res.approval_required is True
    assert state.get_decision(res.decision_id).status is DecisionStatus.AWAITING_APPROVAL


def test_escalate_external_high_risk(gov):
    # dış aksiyon + kanıt yok → risk yüksek → owner KARAR versin
    res = gov.decide(_req(reversibility=EXTERNAL, evidence_refs=[]))
    assert res.verdict is Verdict.ESCALATE
    assert res.approval_required is True
    assert "escalate" in res.rationale


# ---- REVISE (soft ihlal, kayıtlanmaz) ----
def test_revise_on_soft_violation_not_recorded(state):
    gov = GovernanceEngine(state, is_budget_exceeded=lambda: True)
    before = len(state.recent_decisions(limit=1000))
    res = gov.decide(_req())
    assert res.verdict is Verdict.REVISE
    assert res.decision_id is None
    assert any(v.rule == "budget" and v.severity == "soft" for v in res.violations)
    assert len(state.recent_decisions(limit=1000)) == before   # defter'e yazılmadı


# ---- Determinizm + LLM-bağımsızlık ----
def test_deterministic_same_input_same_verdict(gov):
    r1 = gov.decide(_req(chosen="x"))
    r2 = gov.decide(_req(chosen="x"))
    assert r1.verdict == r2.verdict
    assert r1.score.to_dict() == r2.score.to_dict()


def test_governance_records_feed_e1_ledger(gov, state):
    gov.decide(_req(chosen="iş A"))
    gov.decide(_req(chosen="iş B"))
    kinds = [d.chosen for d in state.recent_decisions()]
    assert "iş B" in kinds and "iş A" in kinds        # E4 → E1 etkileşimi
