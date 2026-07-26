"""MIO Core · Cognitive Identity (ADR-0002 Madde 11) — üretim testleri (deterministik, LLM-siz).

MIO'nun kendi bilişsel durumunu bilmesi: neden bu karar / hangi inanç / hangi kanıt / ne kadar emin /
alternatifler / hedefe hizmet / ilkeyle çelişki. Hepsi mevcut Executive verisinden türetilir.
"""

import pytest

from mio_core.born import default_purpose
from mio_core.executive import (
    CognitiveEngine,
    CognitiveIdentity,
    DecisionStatus,
    ExecutiveState,
    SQLiteBeliefStore,
    SQLiteExecutiveStateStore,
)


@pytest.fixture
def state(tmp_path):
    s = SQLiteExecutiveStateStore(str(tmp_path / "e.db"))
    st = ExecutiveState(s)
    st.ensure_identity("MIO")
    st.ensure_purpose(default_purpose())          # "Para harcamak çözüm değildir." ilkesi dahil
    yield st
    s.close()


@pytest.fixture
def cog(tmp_path):
    s = SQLiteBeliefStore(str(tmp_path / "c.db"))
    yield CognitiveEngine(s)
    s.close()


def test_introspect_answers_core_questions(state):
    d = state.record_decision("start_plan", "içerik takvimi kur",
                              rationale="büyümeye hizmet ediyor", options=["reklam", "içerik"],
                              expectation="+trafik", evidence_refs=["mem:trend"],
                              score={"confidence": 0.8})
    ci = CognitiveIdentity(state)
    r = ci.introspect(d.id)
    assert r.why == "büyümeye hizmet ediyor"
    assert r.confidence == 0.8
    assert r.alternatives == ["reklam", "içerik"]
    assert r.evidence == ["mem:trend"]
    assert r.expectation == "+trafik"


def test_related_beliefs_linked(state, cog):
    cog.observe("reklam", "Reklam doğru hedeflenirse büyümeyi hızlandırır.", domain="business", valence=0.7)
    d = state.record_decision("adopt", "reklam kampanyası başlat", rationale="reklam ile büyüme")
    r = CognitiveIdentity(state, cognitive=cog).introspect(d.id)
    assert any("Reklam" in b["statement"] for b in r.related_beliefs)


def test_principle_conflict_on_spending(state):
    d = state.record_decision("tool_use", "ödeme yap: reklam bütçesi", rationale="hızlı sonuç için harca")
    r = CognitiveIdentity(state).introspect(d.id)
    assert r.principle_conflict is True
    assert any(p["status"] == "potential_conflict" for p in r.principle_check)


def test_no_conflict_on_free_action(state):
    d = state.record_decision("start_plan", "ücretsiz içerik üret", rationale="organik büyüme")
    r = CognitiveIdentity(state).introspect(d.id)
    assert r.principle_conflict is False


def test_serves_active_goal(state):
    state.track_goal("g1")
    d = state.record_decision("start_plan", "iş", evidence_refs=["goal:g1"])
    r = CognitiveIdentity(state).introspect(d.id)
    assert r.serves_active_goal is True
    d2 = state.record_decision("start_plan", "ilgisiz iş", evidence_refs=["mem:x"])
    assert CognitiveIdentity(state).introspect(d2.id).serves_active_goal is None  # belirlenemedi (dürüst)


def test_flags_low_confidence_and_conflict(state):
    state.record_decision("k", "normal iş", score={"confidence": 0.9})
    state.record_decision("k", "belirsiz iş", score={"confidence": 0.2})     # düşük güven
    state.record_decision("tool_use", "para harca", rationale="satın al")    # ilke çelişkisi
    flags = CognitiveIdentity(state).flags()
    chosen = {f.chosen for f in flags}
    assert "belirsiz iş" in chosen and "para harca" in chosen and "normal iş" not in chosen


def test_missing_decision_returns_none(state):
    assert CognitiveIdentity(state).introspect("yok") is None
