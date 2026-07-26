"""MIO Core · Goal Management Domain (Faz 1 · Domain 7) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek E2 GoalManager + SQLiteGoalStore üzerinden. Validation, authorization,
hiyerarşi (hedef→milestone→görev), deterministik ilerleme/otomatik tamamlanma, E2 ValueError→domain hata
çevirimi, events ve uçtan-uca akış (E1 senkron dahil) doğrulanır."""

import pytest

from mio_core.domains.goal_management import (
    GoalManagementDomain,
    GoalMgmtEvents,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus
from mio_core.executive.goals import GoalManager, SQLiteGoalStore


def _build():
    store = SQLiteGoalStore(":memory:")
    mgr = GoalManager(store)
    bus = EventBus(record=True)
    dom = GoalManagementDomain(mgr, store, bus=bus)
    return dom, store, bus


@pytest.fixture
def gd():
    return _build()


# ---- UNIT: validation ----
def test_define_validation(gd):
    d, _s, _b = gd
    with pytest.raises(ValidationError):
        d.define_goal("owner", "  ", 90)                 # boş metin
    with pytest.raises(ValidationError):
        d.define_goal("owner", "hedef", 0)               # ufuk dışı (E2 ValueError → ValidationError)
    with pytest.raises(ValidationError):
        d.define_goal("owner", "hedef", 5000)


# ---- UNIT: authorization ----
def test_authorization(gd):
    d, _s, _b = gd
    with pytest.raises(UnauthorizedError):
        d.define_goal("yabanci", "hedef", 90)
    with pytest.raises(UnauthorizedError):
        d.tree("yabanci", "x")


# ---- INTEGRATION: milestone ufuk + bulunamadı çevirimi ----
def test_milestone_horizon_and_notfound(gd):
    d, _s, _b = gd
    g = d.define_goal("owner", "büyüme", 30)
    with pytest.raises(ValidationError):
        d.add_milestone("owner", g["id"], "M", 60)       # ufuk dışı → ValidationError
    with pytest.raises(NotFoundError):
        d.add_milestone("owner", "yok-goal", "M", 10)    # 'bulunamadı' → NotFoundError


# ---- INTEGRATION: hiyerarşi + deterministik ilerleme/otomatik tamamlanma ----
def test_full_hierarchy_progress_and_completion(gd):
    d, store, bus = gd
    g = d.define_goal("Executive", "aylık 5000$ gelir", 90)
    m = d.add_milestone("Executive", g["id"], "landing yayında", 30)
    t1 = d.add_task("Executive", g["id"], m["id"], "sayfa tasarla")
    t2 = d.add_task("Executive", g["id"], m["id"], "reklam kur")
    assert d.progress("owner", g["id"])["progress"] == 0.0
    d.record_result("Executive", t1["id"], "completed")
    d.record_result("Executive", t2["id"], "completed")
    assert d.progress("owner", g["id"])["progress"] == 1.0
    assert store.get_goal(g["id"]).status == "completed"          # otomatik tamamlandı
    tree = d.tree("owner", g["id"])
    assert tree["milestones"][0]["status"] == "completed" and len(tree["milestones"][0]["tasks"]) == 2
    types = [e["type"] for e in bus.history()]
    assert GoalMgmtEvents.GOAL_COMPLETED in types and GoalMgmtEvents.TASK_RESULT in types


def test_record_result_validation(gd):
    d, _s, _b = gd
    g = d.define_goal("owner", "h", 30)
    m = d.add_milestone("owner", g["id"], "M", 10)
    t = d.add_task("owner", g["id"], m["id"], "görev")
    with pytest.raises(ValidationError):
        d.record_result("owner", t["id"], "geçersiz-statü")
    with pytest.raises(NotFoundError):
        d.record_result("owner", "yok-task", "completed")


# ---- INTEGRATION: abandon + list + stats + contract ----
def test_abandon_list_stats_contract(gd):
    d, _s, bus = gd
    g = d.define_goal("owner", "vazgeçilecek", 60)
    d.abandon("owner", g["id"], reason="öncelik değişti")
    assert d.list_goals("owner", status="abandoned")[0]["id"] == g["id"]
    assert any(e["type"] == GoalMgmtEvents.GOAL_ABANDONED for e in bus.history())
    with pytest.raises(ValidationError):
        d.list_goals("owner", status="uydurma")
    s = d.stats()
    assert s["total"] >= 1 and s["goals_abandoned"] >= 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "goal_management" and "define_goal" in c["operations"]


# ---- SMOKE: boot() → domain uçtan uca + E1 senkron + paylaşılan store ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    g = mio.goal_management.define_goal("owner", "aylık gelir hedefi", 90)
    # paylaşılan store + E1 aktif indeks aynı hedefi görür (tek doğruluk kaynağı, E1 senkron)
    assert any(x["id"] == g["id"] for x in mio.goal_management.list_goals("owner"))
    assert g["id"] in [gg.goal_id for gg in mio.state.active_goals()]
    m = mio.goal_management.add_milestone("owner", g["id"], "MVP", 30)
    t = mio.goal_management.add_task("owner", g["id"], m["id"], "ilk sürüm")
    mio.goal_management.record_result("owner", t["id"], "completed")
    assert mio.goal_management.progress("owner", g["id"])["progress"] == 1.0
    assert mio.goal_management.contract()["version"] == "1.0.0"
    mio.close()
