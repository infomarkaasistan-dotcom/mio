"""MIO Core · Scheduler/Lifecycle Domain (Faz 4 · Domain 12) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite koşu deposu üzerinden. Deterministik tick/sıralama, interval zamanlama,
one_shot, LoopGuard (devre kesici + tavan), zombie-guard, yaşam-döngüsü, authorization, events ve uçtan-uca
akış doğrulanır. Duvar-saati thread yok — tamamen deterministik."""

import pytest

from mio_core.domains.scheduler import (
    LifecycleState,
    RunStatus,
    ScheduleRepository,
    ScheduleRun,
    SchedEvents,
    SchedulerConfig,
    SchedulerDomain,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(config=None):
    repo = ScheduleRepository(":memory:")
    bus = EventBus(record=True)
    dom = SchedulerDomain(repo, bus=bus, config=config)
    return dom, repo, bus


@pytest.fixture
def sch():
    return _build()


# ---- UNIT: validation + authorization ----
def test_register_validation(sch):
    d, _r, _b = sch
    d.register_job("owner", "j", lambda: None)
    with pytest.raises(ValidationError):
        d.register_job("owner", "j", lambda: None)          # tekrar
    with pytest.raises(ValidationError):
        d.register_job("owner", "  ", lambda: None)         # boş ad
    with pytest.raises(ValidationError):
        d.register_job("owner", "k", lambda: None, interval=0)
    with pytest.raises(ValidationError):
        d.register_job("owner", "m", "değil-callable")


def test_authorization(sch):
    d, _r, _b = sch
    with pytest.raises(UnauthorizedError):
        d.tick("yabanci")
    with pytest.raises(UnauthorizedError):
        d.jobs("yabanci")


# ---- INTEGRATION: deterministik tick + sıralama ----
def test_tick_runs_due_jobs_in_order(sch):
    d, _r, bus = sch
    order = []
    d.register_job("owner", "a", lambda: order.append("a"))
    d.register_job("owner", "b", lambda: order.append("b"))
    out = d.tick("owner")
    assert out["clock"] == 1 and [r["job"] for r in out["ran"]] == ["a", "b"]  # kayıt sırası
    assert order == ["a", "b"]
    assert any(e["type"] == SchedEvents.TICK for e in bus.history())


def test_interval_scheduling(sch):
    d, _r, _b = sch
    runs = []
    d.register_job("owner", "her2", lambda: runs.append(1), interval=2)
    d.tick("owner")                                         # clock 1 → vadesi değil (next_due=2)
    assert runs == []
    d.tick("owner")                                         # clock 2 → çalışır
    assert runs == [1]


def test_one_shot(sch):
    d, _r, _b = sch
    runs = []
    d.register_job("owner", "bir", lambda: runs.append(1), one_shot=True)
    d.tick("owner"); d.tick("owner")
    assert runs == [1]                                      # yalnız bir kez
    assert d.jobs("owner")[0]["enabled"] is False


# ---- INTEGRATION: LoopGuard devre kesici ----
def test_loopguard_disables_after_failures(sch):
    d, _r, bus = sch
    def boom():
        raise RuntimeError("hata")
    d.register_job("owner", "kırık", boom, max_failures=2)
    d.tick("owner")                                         # fail 1
    assert d.jobs("owner")[0]["enabled"] is True
    out = d.tick("owner")                                   # fail 2 → devre açılır
    assert "kırık" in out["disabled"] and d.jobs("owner")[0]["enabled"] is False
    assert any(e["type"] == SchedEvents.JOB_DISABLED for e in bus.history())
    d.tick("owner")                                         # devre açık → çalışmaz (koşu artmaz)


def test_success_resets_failures(sch):
    d, _r, _b = sch
    state = {"fail": True}
    def flaky():
        if state["fail"]:
            raise RuntimeError("x")
    d.register_job("owner", "flaky", flaky, max_failures=3)
    d.tick("owner")                                         # fail → failures=1
    assert d.jobs("owner")[0]["failures"] == 1
    state["fail"] = False
    d.tick("owner")                                         # success → failures sıfırlanır
    assert d.jobs("owner")[0]["failures"] == 0


def test_loopguard_ceiling():
    d, _r, _b = _build(SchedulerConfig(max_runs_per_tick=1))
    ran = []
    d.register_job("owner", "a", lambda: ran.append("a"))
    d.register_job("owner", "b", lambda: ran.append("b"))
    out = d.tick("owner")
    assert out["executions"] == 1 and len(ran) == 1        # tavan: tick başına 1 yürütme


# ---- INTEGRATION: yaşam-döngüsü ----
def test_lifecycle_gates_execution(sch):
    d, _r, _b = sch
    runs = []
    d.register_job("owner", "j", lambda: runs.append(1))
    d.pause("owner")
    assert d.tick("owner")["ran"] == [] and runs == []     # duraklatılmış → çalışmaz
    d.resume("owner")
    d.tick("owner")
    assert runs == [1]
    d.stop("owner")
    d.tick("owner")
    assert runs == [1]                                     # durduruldu → artmaz


def test_run_now_ignores_schedule(sch):
    d, _r, _b = sch
    runs = []
    d.register_job("owner", "j", lambda: runs.append(1), interval=100)
    r = d.run_now("owner", "j")
    assert r["status"] == RunStatus.COMPLETED and runs == [1]
    with pytest.raises(NotFoundError):
        d.run_now("owner", "yok")


# ---- INTEGRATION: zombie-guard ----
def test_zombie_guard_reaps_running(sch):
    d, repo, bus = sch
    repo.put(ScheduleRun(job="çökmüş", tick=5, status=RunStatus.RUNNING))   # önceki süreçten kalan
    res = d.reap_zombies("owner")
    assert res["reaped"] == 1
    assert repo.list_by_status(RunStatus.RUNNING) == []
    assert any(e["type"] == SchedEvents.ZOMBIE_REAPED for e in bus.history())


# ---- INTEGRATION: history + stats + contract ----
def test_history_stats_contract(sch):
    d, _r, _b = sch
    d.register_job("owner", "j", lambda: "tamam")
    d.tick("owner")
    hist = d.run_history("owner", job="j")
    assert hist and hist[0]["status"] == RunStatus.COMPLETED
    assert d.explain("owner", hist[0]["id"])["job"] == "j"
    s = d.stats()
    assert s["jobs"] == 1 and s["completed"] >= 1 and s["state"] == LifecycleState.RUNNING
    assert s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "scheduler" and "tick" in c["operations"]


# ---- SMOKE: boot() → doğuştan öz-bakım işleri + otonom tick ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    names = [j["name"] for j in mio.scheduler.jobs("owner")]
    assert {"memory_consolidation", "executive_review", "learning_consolidation"} <= set(names)
    # öz-bakım işi elle tetiklenebilir (deterministik, LLM yok)
    r = mio.scheduler.run_now("owner", "memory_consolidation")
    assert r["status"] == RunStatus.COMPLETED
    out = mio.scheduler.tick("owner")                        # otonom tick çalışır
    assert out["clock"] == 1 and mio.scheduler.stats()["state"] == LifecycleState.RUNNING
    assert mio.scheduler.contract()["version"] == "1.0.0"
    mio.close()
