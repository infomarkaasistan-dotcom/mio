"""MIO Core · E2 Goal Management — üretim testleri (deterministik, LLM-siz).

Hiyerarşi + ufuk-dışı reddi + deterministik ilerleme + E1 senkron + E2→E3 progress entegrasyonu.
"""

import pytest

from mio_core.executive import (
    ExecutiveReview,
    ExecutiveState,
    GoalManager,
    GoalProgressSignals,
    GoalStore,
    GovernanceEngine,
    ReviewVerdict,
    SQLiteExecutiveStateStore,
    SQLiteGoalStore,
)


@pytest.fixture
def gstore(tmp_path):
    s = SQLiteGoalStore(str(tmp_path / "goals.db"))
    yield s
    s.close()


@pytest.fixture
def state(tmp_path):
    s = SQLiteExecutiveStateStore(str(tmp_path / "exec.db"))
    st = ExecutiveState(s)
    st.ensure_identity("MIO")
    yield st
    s.close()


@pytest.fixture
def gm(gstore, state):
    return GoalManager(gstore, executive_state=state)


# ---- Oluşturma + E1 senkron ----
def test_create_goal_tracks_in_e1(gm, state):
    g = gm.create_goal("aylık 5000$ gelir", horizon_days=90)
    assert g.status == "active"
    assert g.id in [x.goal_id for x in state.active_goals()]   # E1 aktif indeksine düştü


def test_create_goal_horizon_validation(gm):
    with pytest.raises(ValueError):
        gm.create_goal("x", horizon_days=0)
    with pytest.raises(ValueError):
        gm.create_goal("x", horizon_days=1000)


# ---- Milestone + ufuk-dışı reddi ----
def test_add_milestone_and_horizon_reject(gm):
    g = gm.create_goal("hedef", 90)
    m = gm.add_milestone(g.id, "ilk çeyrek", 30)
    assert m.target_day_offset == 30
    with pytest.raises(ValueError):
        gm.add_milestone(g.id, "ufuk dışı", 120)   # 120 > 90


def test_propose_milestones_filters_invalid(gm):
    g = gm.create_goal("hedef", 90)

    def proposer(text, horizon):
        return [{"title": "geçerli", "target_day_offset": 30},
                {"title": "ufuk dışı", "target_day_offset": 200},   # elenmeli
                {"title": "", "target_day_offset": 10},             # başlıksız → elenmeli
                {"bozuk": True}]                                     # geçersiz → elenmeli

    added = gm.propose_milestones(g.id, proposer=proposer)
    assert [m.title for m in added] == ["geçerli"]


def test_propose_without_proposer_is_honest_empty(gm):
    g = gm.create_goal("hedef", 90)
    assert gm.propose_milestones(g.id) == []       # danışman yok → uydurma yok


# ---- Görev + aktivasyon ----
def test_add_and_activate_task(gm):
    g = gm.create_goal("hedef", 90)
    m = gm.add_milestone(g.id, "ms", 30)
    t = gm.add_task(g.id, m.id, "landing page üret")
    assert t.status == "pending"
    activated = gm.activate_task(t.id)             # interpreter yok
    assert activated.status == "activated" and "workflow_id" not in activated.result_summary


def test_activate_task_with_interpreter(gm):
    g = gm.create_goal("hedef", 90)
    m = gm.add_milestone(g.id, "ms", 30)
    t = gm.add_task(g.id, m.id, "iş")
    activated = gm.activate_task(t.id, interpreter=lambda task: "wf-123")
    assert activated.status == "running" and activated.result_summary["workflow_id"] == "wf-123"


# ---- Deterministik ilerleme: görev→milestone→hedef ----
def test_completion_cascades_to_goal_and_e1(gm, state):
    g = gm.create_goal("hedef", 90)
    m = gm.add_milestone(g.id, "ms", 30)
    t1 = gm.add_task(g.id, m.id, "a")
    t2 = gm.add_task(g.id, m.id, "b")
    gm.record_task_result(t1.id, "completed")
    assert gm._store.get_milestone(m.id).status != "completed"   # henüz b bitmedi
    gm.record_task_result(t2.id, "completed")
    assert gm._store.get_milestone(m.id).status == "completed"
    assert gm._store.get_goal(g.id).status == "completed"         # tüm milestone bitti → hedef bitti
    # E1 senkron: hedef artık aktif değil
    assert g.id not in [x.goal_id for x in state.active_goals()]


def test_abandon_goal_untracks_e1(gm, state):
    g = gm.create_goal("hedef", 90)
    gm.abandon_goal(g.id)
    assert gm._store.get_goal(g.id).status == "abandoned"
    assert g.id not in [x.goal_id for x in state.active_goals()]


# ---- Ağaç + ilerleme oranı ----
def test_goal_tree_and_progress(gm):
    g = gm.create_goal("hedef", 90)
    m = gm.add_milestone(g.id, "ms", 30)
    t1 = gm.add_task(g.id, m.id, "a")
    gm.add_task(g.id, m.id, "b")
    tree = gm.goal_tree(g.id)
    assert tree["goal"]["id"] == g.id
    assert len(tree["milestones"][0]["tasks"]) == 2
    assert gm.progress(g.id) == 0.0
    gm.record_task_result(t1.id, "completed")
    assert gm.progress(g.id) == 0.5


def test_store_satisfies_protocol(gstore):
    assert isinstance(gstore, GoalStore)


# ---- E2 → E3: gerçek ilerleme sinyali review'ı besler ----
def test_progress_signal_drives_review(gm, state):
    gov = GovernanceEngine(state)
    g = gm.create_goal("aylık gelir", 90)
    state.set_strategy(g.id, "içerik + reklam")
    m = gm.add_milestone(g.id, "ms", 30)
    gm.add_task(g.id, m.id, "iş")                  # 0 tamamlanmış → progress 0.0
    review = ExecutiveReview(state, gov, signals=GoalProgressSignals(gm))
    gr = next(x for x in review.run().goal_reviews if x.goal_id == g.id)
    assert gr.verdict is ReviewVerdict.REVISE_STRATEGY   # düşük ilerleme → strateji revize
