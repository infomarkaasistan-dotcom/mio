"""MIO Core · E1 Persistent Executive State — üretim testleri (gerçek SQLite, mock YOK)."""

import pytest

from mio_core.executive import (
    Decision,
    DecisionStatus,
    ExecutiveState,
    ExecutiveStateStore,
    SQLiteExecutiveStateStore,
    StrategyStatus,
)


@pytest.fixture
def store(tmp_path):
    s = SQLiteExecutiveStateStore(str(tmp_path / "state.db"))
    yield s
    s.close()


@pytest.fixture
def state(store):
    return ExecutiveState(store)


# ---- Kimlik: tekil, sürekli ----
def test_identity_singleton_and_continuity(state):
    a = state.ensure_identity("MIO", nature="Executive OS")
    b = state.ensure_identity("BAŞKA", nature="x")  # zaten var → mevcut döner
    assert a.id == b.id and b.name == "MIO"          # ikinci çağrı yeni kimlik YARATMAZ
    assert b.version == 1


def test_evolve_identity_versioned(state):
    a = state.ensure_identity("MIO")
    b = state.evolve_identity(nature="daha olgun")
    assert b.id == a.id and b.born_at == a.born_at    # soy korunur
    assert b.version == 2 and b.nature == "daha olgun"


# ---- Misyon: sürümlü ----
def test_mission_versioning(state):
    m1 = state.set_mission("Uzun vadeli hedefleri yönet", value_priorities=["dürüstlük"])
    m2 = state.set_mission("Uzun vadeli hedefleri yönet + öğren", rationale="genişletme")
    assert m1.version == 1 and m2.version == 2
    assert state.get_mission().statement.endswith("öğren")


# ---- Hedef referansları ----
def test_goal_tracking(state):
    state.track_goal("g1", horizon_days=90)
    state.track_goal("g2", status="completed")
    active = state.active_goals()
    assert {g.goal_id for g in active} == {"g1"}
    state.untrack_goal("g1")
    assert state.active_goals() == []


# ---- Stratejiler: set önceyi arşivler, geçmiş korunur ----
def test_set_strategy_revises_previous(state):
    s1 = state.set_strategy("g1", "içerik üret", rationale="ilk")
    s2 = state.set_strategy("g1", "reklam ver", rationale="pivot")
    assert state.get_strategy("g1").id == s2.id                 # aktif = yeni
    history = store_history(state, "g1")
    assert history[s1.id] == StrategyStatus.REVISED.value       # eski arşivlendi (silinmedi)
    assert history[s2.id] == StrategyStatus.ACTIVE.value


def test_retire_strategy(state):
    state.set_strategy("g1", "içerik üret")
    retired = state.retire_strategy("g1", rationale="hedef değişti")
    assert retired.status == StrategyStatus.ABANDONED
    assert state.get_strategy("g1") is None


def store_history(state, goal_id):
    return {s.id: s.status.value for s in state._store.list_strategies(goal_id=goal_id)}


# ---- Karar defteri + DEFER + tam öğrenme zinciri ----
def test_record_and_recent_decisions(state):
    d = state.record_decision("start_plan", "landing page üret",
                              rationale="hedefe hizmet ediyor", expectation="+50 ziyaretçi/gün",
                              evidence_refs=["mem:trend-1"])
    assert d.status == DecisionStatus.COMMITTED
    recent = state.recent_decisions()
    assert recent and recent[0].id == d.id


def test_defer_decision(state):
    d = state.defer_decision("adopt_strategy", rationale="yeterli veri yok",
                             needed_evidence=["pazar boyutu", "rakip fiyatı"])
    assert d.status == DecisionStatus.DEFERRED and d.chosen == "defer"
    assert d.score["needed_evidence"] == ["pazar boyutu", "rakip fiyatı"]
    deferred = state.deferred_decisions()
    assert [x.id for x in deferred] == [d.id]


def test_link_outcome_closes_learning_chain(state):
    # Expectation → Decision → Evidence → Outcome → Prediction Error → Belief Update
    d = state.record_decision("start_plan", "reklam kampanyası",
                              expectation="ROAS 3.0", evidence_refs=["mem:gecmis-roas"])
    updated = state.link_outcome(
        d.id, outcome={"roas": 1.4, "note": "beklenenin altında"},
        prediction_error=1.6, belief_update_refs=["belief:reklam-verimi"])
    assert updated.outcome["roas"] == 1.4
    assert updated.prediction_error == pytest.approx(1.6)
    assert updated.belief_update_refs == ["belief:reklam-verimi"]
    # Karar SİLİNMEDİ, zincir eklendi; gerekçe/beklenti korunmuş
    persisted = state._store.get_decision(d.id)
    assert persisted.expectation == "ROAS 3.0" and persisted.evidence_refs == ["mem:gecmis-roas"]


def test_link_outcome_missing_raises(state):
    with pytest.raises(KeyError):
        state.link_outcome("yok", outcome={})


# ---- Dersler + deterministik ilgi araması ----
def test_lessons_and_relevant_search(state):
    state.record_lesson("Reklam bütçesini erken artırma", source="prediction_error",
                        applies_to=["reklam", "bütçe"])
    state.record_lesson("İçerik tutarlılığı büyümeyi hızlandırır", applies_to=["içerik"])
    hits = state.relevant_lessons("reklam bütçesi stratejisi")
    assert hits and "Reklam" in hits[0].text        # ilgili ders en üstte
    assert state.relevant_lessons("kuantum fiziği") == []  # ilgisizde uydurmaz


# ---- consult / snapshot ----
def test_consult_assembles_context(state):
    state.ensure_identity("MIO")
    state.set_mission("uzun vadeli hedef yönetimi")
    state.track_goal("g1")
    state.set_strategy("g1", "reklam ver")
    state.record_lesson("reklam dersi", applies_to=["reklam"])
    ctx = state.consult("reklam kararı")
    assert ctx.identity.name == "MIO"
    assert ctx.mission is not None
    assert [g.goal_id for g in ctx.active_goals] == ["g1"]
    assert ctx.active_strategies[0].approach == "reklam ver"
    assert ctx.relevant_lessons  # konuyla ilgili ders geldi


def test_snapshot_counts(state):
    state.track_goal("g1")
    state.track_goal("g2", status="completed")
    state.record_decision("k", "x")
    state.defer_decision("y", rationale="veri yok")
    state.record_lesson("ders")
    view = state.snapshot()
    assert view.counts["goals"] == 2
    assert view.counts["active_goals"] == 1
    assert view.counts["decisions"] == 2
    assert view.counts["deferred_decisions"] == 1
    assert view.counts["lessons"] == 1


# ---- Kalıcılık: konuşma gelir-geçer, state kalır ----
def test_persistence_across_reopen(tmp_path):
    path = str(tmp_path / "s.db")
    s1 = SQLiteExecutiveStateStore(path)
    st1 = ExecutiveState(s1)
    st1.ensure_identity("MIO", nature="sürekli")
    st1.record_decision("k", "x", rationale="kalıcı olmalı")
    s1.close()
    # Yeni "oturum" — aynı depo
    s2 = SQLiteExecutiveStateStore(path)
    st2 = ExecutiveState(s2)
    assert st2.get_identity().name == "MIO"
    assert st2.recent_decisions()[0].rationale == "kalıcı olmalı"
    s2.close()


# ---- Sözleşme uyumu (adaptör soyutlaması) ----
def test_sqlite_store_satisfies_protocol(store):
    assert isinstance(store, ExecutiveStateStore)
