"""MIO Core · E3 Executive Review — üretim testleri (deterministik, LLM-siz).

Goal Review + Belief Revision + Evidence Acquisition; hepsi E4 governance üzerinden E1'e yazar.
Enjekte edilen sinyaller/belief-source/evidence-gatherer GERÇEK adaptör implementasyonlarıdır
(test double), sistemin kendisinde mock/placeholder YOKTUR.
"""

import pytest

from mio_core.executive import (
    DecisionRequest,
    DecisionStatus,
    ExecutiveReview,
    ExecutiveState,
    GovernanceEngine,
    ReviewVerdict,
    SQLiteExecutiveStateStore,
    Verdict,
)


# ---- test double adaptörleri (E3'ün opsiyonel bağımlılıkları) ----
class FakeSignals:
    def __init__(self, meaningful=None, progress=None, risk=None):
        self._m, self._p, self._r = meaningful, progress, risk

    def meaningful(self, goal_id): return self._m
    def progress(self, goal_id): return self._p
    def risk(self, goal_id): return self._r


class FakeBeliefSource:
    def __init__(self, flagged):
        self._flagged = flagged
        self.revised = []

    def flagged_for_revision(self): return self._flagged
    def mark_revised(self, belief_id, note=""): self.revised.append((belief_id, note))


class FakeGatherer:
    def __init__(self, refs):
        self._refs = refs
        self.calls = []

    def gather(self, needed_evidence, context_ref=""):
        self.calls.append(list(needed_evidence))
        return list(self._refs)


@pytest.fixture
def state(tmp_path):
    s = SQLiteExecutiveStateStore(str(tmp_path / "e3.db"))
    st = ExecutiveState(s)
    st.ensure_identity("MIO")
    st.set_mission("uzun vadeli hedef yönetimi")
    yield st
    s.close()


@pytest.fixture
def gov(state):
    return GovernanceEngine(state)


# ---- 1) Goal Review ----
def test_goal_continue(state, gov):
    state.track_goal("g1")
    state.set_strategy("g1", "içerik üret")
    review = ExecutiveReview(state, gov, signals=FakeSignals(meaningful=True, progress=0.5, risk=0.2))
    gr = _goal(review.run(), "g1")
    assert gr.verdict is ReviewVerdict.CONTINUE and gr.decision_id is None


def test_goal_revise_when_no_strategy(state, gov):
    state.track_goal("g2")                       # strateji yok
    review = ExecutiveReview(state, gov)
    gr = _goal(review.run(), "g2")
    assert gr.verdict is ReviewVerdict.REVISE_STRATEGY
    assert gr.decision_id and state.get_decision(gr.decision_id) is not None  # E3→E4→E1


def test_goal_abandon_when_not_meaningful(state, gov):
    state.track_goal("g1")
    state.set_strategy("g1", "x")
    review = ExecutiveReview(state, gov, signals=FakeSignals(meaningful=False))
    gr = _goal(review.run(), "g1")
    assert gr.verdict is ReviewVerdict.ABANDON_GOAL
    assert gr.governance_verdict == Verdict.APPROVE.value
    assert "g1" not in [g.goal_id for g in state.active_goals()]   # onaylı → state'ten düşürüldü


def test_goal_escalate_high_risk(state, gov):
    state.track_goal("g1")
    state.set_strategy("g1", "x")
    review = ExecutiveReview(state, gov, signals=FakeSignals(meaningful=True, risk=0.85))
    gr = _goal(review.run(), "g1")
    assert gr.verdict is ReviewVerdict.ESCALATE and gr.decision_id is not None


# ---- 2) Belief Revision ----
def test_belief_revision_active(state, gov):
    bs = FakeBeliefSource([{"id": "b1", "statement": "reklam hep işe yarar",
                            "reason": "prediction-error yüksek"}])
    review = ExecutiveReview(state, gov, belief_source=bs)
    report = review.run()
    assert len(report.belief_reviews) == 1
    br = report.belief_reviews[0]
    assert br.belief_id == "b1" and br.action == "revised"
    assert bs.revised == [("b1", "prediction-error yüksek")]        # kaynağa bildirildi
    assert state.get_decision(br.decision_id).kind == "belief_revision"


def test_belief_revision_inactive_without_source(state, gov):
    review = ExecutiveReview(state, gov)
    assert review.run().belief_reviews == []                        # provider yok → pasif (dürüst)


# ---- 3) Evidence Acquisition ----
def test_evidence_pending_without_gatherer(state, gov):
    state.track_goal("g1")
    state.set_strategy("g1", "x")
    d = gov.decide(DecisionRequest(kind="adopt", chosen="strateji X", goal_id="g1",
                                   needs_evidence=True, needed_evidence=["pazar boyutu"]))
    assert d.verdict is Verdict.DEFER
    review = ExecutiveReview(state, gov)          # gatherer yok
    ereq = _evidence(review.run(), d.decision_id)
    assert ereq.status == "pending" and ereq.needed_evidence == ["pazar boyutu"]


def test_evidence_fulfilled_triggers_resubmit(state, gov):
    state.track_goal("g1")
    state.set_strategy("g1", "x")
    d = gov.decide(DecisionRequest(kind="adopt", chosen="strateji X", goal_id="g1",
                                   needs_evidence=True, needed_evidence=["pazar boyutu"]))
    gatherer = FakeGatherer(refs=["mem:pazar-raporu"])
    review = ExecutiveReview(state, gov, evidence_gatherer=gatherer)
    ereq = _evidence(review.run(), d.decision_id)
    assert ereq.status == "fulfilled" and ereq.gathered_refs == ["mem:pazar-raporu"]
    assert gatherer.calls == [["pazar boyutu"]]
    # Eski DEFER kapatıldı (superseded), taze kanıtla yeni karar üretildi
    assert state.get_decision(d.decision_id).status is DecisionStatus.SUPERSEDED
    resub = state.get_decision(ereq.resubmitted_decision_id)
    assert resub is not None and resub.evidence_refs == ["mem:pazar-raporu"]
    assert resub.chosen == "strateji X"           # orijinal eylem korunmuştu → yeniden sunuldu


def test_report_serializes(state, gov):
    state.track_goal("g1")
    review = ExecutiveReview(state, gov)
    d = review.run().to_dict()
    assert d["trigger"] == "periodic" and "goal_reviews" in d and "evidence_requests" in d


# ---- yardımcılar ----
def _goal(report, goal_id):
    return next(g for g in report.goal_reviews if g.goal_id == goal_id)


def _evidence(report, decision_id):
    return next(e for e in report.evidence_requests if e.decision_id == decision_id)
