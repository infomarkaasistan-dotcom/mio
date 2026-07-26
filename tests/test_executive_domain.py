"""MIO Core · Executive Domain (Faz 1 · Domain 1) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek E1-E5 üzerinden. Domain iş kuralları, authorization, validation, events,
audit ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.executive import (
    DecisionCommand,
    ExecutiveDomain,
    ExecEvents,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus
from mio_core.executive import (
    CognitiveEngine,
    CognitiveIdentity,
    ExecutiveReview,
    ExecutiveState,
    GoalManager,
    GovernanceEngine,
    Purpose,
    SQLiteBeliefStore,
    SQLiteExecutiveStateStore,
    SQLiteGoalStore,
)


def _build():
    state = ExecutiveState(SQLiteExecutiveStateStore(":memory:"))
    state.ensure_identity("MIO")
    state.ensure_purpose(Purpose(primary_objective="gelir"))
    goals = GoalManager(SQLiteGoalStore(":memory:"), executive_state=state)
    gov = GovernanceEngine(state)
    cog = CognitiveEngine(SQLiteBeliefStore(":memory:"))
    review = ExecutiveReview(state, gov, belief_source=cog)
    cid = CognitiveIdentity(state, cognitive=cog)
    bus = EventBus(record=True)
    dom = ExecutiveDomain(state=state, goals=goals, governance=gov, review=review,
                          cognitive_identity=cid, bus=bus)
    return dom, state, bus


@pytest.fixture
def dom():
    return _build()


# ---- UNIT: validation ----
def test_set_goal_validation(dom):
    d, _s, _b = dom
    with pytest.raises(ValidationError):
        d.set_goal("owner", "  ", 90)                    # boş metin
    with pytest.raises(ValidationError):
        d.set_goal("owner", "hedef", 0)                  # ufuk dışı
    with pytest.raises(ValidationError):
        d.set_goal("owner", "hedef", 5000)


def test_decide_validation(dom):
    d, _s, _b = dom
    with pytest.raises(ValidationError):
        d.decide("owner", DecisionCommand(kind="", chosen="x"))


# ---- UNIT: authorization ----
def test_authorization_rules(dom):
    d, _s, _b = dom
    with pytest.raises(UnauthorizedError):
        d.set_goal("yabanci", "hedef", 90)               # kayıtsız aktör
    with pytest.raises(UnauthorizedError):
        d.abandon_goal("Marketing", "g1")                # owner-only op, brain çağırdı
    with pytest.raises(UnauthorizedError):
        d.set_mission("Finance", "misyon")               # owner-only


# ---- UNIT: goal + event + audit ----
def test_set_goal_tracks_and_emits(dom):
    d, state, bus = dom
    out = d.set_goal("owner", "aylık 5000$ gelir", 90)
    assert out.goal_id and out.status == "active"
    assert out.goal_id in [g.goal_id for g in state.active_goals()]      # E1'e track edildi
    assert any(e["type"] == ExecEvents.GOAL_SET for e in bus.history())  # event yayınlandı


# ---- INTEGRATION: decide → E4 governance + E1 audit + introspect ----
def test_decide_governance_audit_introspect(dom):
    d, state, bus = dom
    goal = d.set_goal("Executive", "büyüme", 90)
    out = d.decide("Executive", DecisionCommand(
        kind="start_plan", chosen="içerik takvimi", goal_id=goal.goal_id,
        expectation="+trafik", evidence_refs=["mem:trend"]))
    assert out.verdict == "approve" and out.decision_id                  # E4 onayladı
    assert state.get_decision(out.decision_id) is not None               # E1 defterine audit'lendi
    assert any(e["type"] == ExecEvents.DECISION_MADE for e in bus.history())
    intro = d.introspect(out.decision_id)                                # E5 iç-gözlem
    assert intro["why"] is not None and intro["evidence"] == ["mem:trend"]


def test_decide_misaligned_rejected(dom):
    d, _s, _b = dom
    out = d.decide("owner", DecisionCommand(kind="start_plan", chosen="x", goal_id="yok"))
    assert out.verdict == "reject"                                       # hizasız → E4 reddetti


def test_abandon_goal_and_not_found(dom):
    d, state, bus = dom
    goal = d.set_goal("owner", "hedef", 90)
    d.abandon_goal("owner", goal.goal_id, reason="değişti")
    assert goal.goal_id not in [g.goal_id for g in state.active_goals()]
    assert any(e["type"] == ExecEvents.GOAL_ABANDONED for e in bus.history())
    with pytest.raises(NotFoundError):
        d.abandon_goal("owner", "yok")


# ---- INTEGRATION: review + mission/purpose + observability ----
def test_review_and_events(dom):
    d, _s, bus = dom
    d.set_goal("owner", "hedef", 90)
    report = d.review("periodic")
    assert "goal_reviews" in report
    assert any(e["type"] == ExecEvents.REVIEW_COMPLETED for e in bus.history())


def test_mission_owner_only_and_metrics(dom):
    d, _s, bus = dom
    m = d.set_mission("owner", "uzun vadeli hedef yönetimi", value_priorities=["dürüstlük"])
    assert m["version"] >= 1 and any(e["type"] == ExecEvents.MISSION_SET for e in bus.history())
    d.set_goal("owner", "h", 30)
    met = d.metrics()
    assert met["goals_set"] >= 1 and met["contract_version"] == "1.0.0"


def test_contract_and_introspect_missing(dom):
    d, _s, _b = dom
    c = d.contract()
    assert c["domain"] == "executive" and c["version"] == "1.0.0" and "decide" in c["operations"]
    with pytest.raises(NotFoundError):
        d.introspect("yok")


# ---- SMOKE: boot() → domain uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    goal = mio.executive.set_goal("owner", "aylık gelir üret", 90)
    out = mio.executive.decide("owner", DecisionCommand(
        kind="start_plan", chosen="landing page", goal_id=goal.goal_id, evidence_refs=["m"]))
    assert out.verdict == "approve"
    assert "goal_reviews" in mio.executive.review()
    assert mio.executive.status()["identity"]["name"] == "MIO"
    assert mio.executive.contract()["version"] == "1.0.0"
    mio.close()
