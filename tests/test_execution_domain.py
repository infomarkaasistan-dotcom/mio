"""MIO Core · Execution Domain (Faz 2 · Domain 9) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek ToolOrchestrator + CapabilityRegistry + PlanningDomain üzerinden. Anayasa
güvencesi (yetkilendirme olmadan yürütme yok), onaylı-plan workflow'u, fail-fast, denetim izi, events ve
uçtan-uca akış doğrulanır."""

import pytest

from mio_core.capability import Capability, CapabilityRegistry
from mio_core.domains.execution import (
    ExecEvents,
    ExecutionDomain,
    ExecutionRepository,
    RunStatus,
    NotFoundError,
    UnauthorizedError,
    UnauthorizedExecutionError,
)
from mio_core.domains.planning import PlanningDomain, PlanRepository
from mio_core.events import EventBus
from mio_core.execution.orchestrator import ToolOrchestrator


class _Echo:
    def execute(self, capability, action, args):
        return {"echoed": args}


class _Boom:
    def execute(self, capability, action, args):
        raise RuntimeError("patladı")


def _build():
    caps = CapabilityRegistry()
    caps.register(Capability(name="echo", description="yankı"))
    caps.register(Capability(name="boom", description="patlar"))
    orch = ToolOrchestrator(caps)                      # governance=None → sade
    orch.register_executor("echo", _Echo())
    orch.register_executor("boom", _Boom())
    bus = EventBus(record=True)
    planning = PlanningDomain(PlanRepository(":memory:"), capabilities=caps)
    ex = ExecutionDomain(orch, ExecutionRepository(":memory:"), planning=planning, bus=bus)
    return ex, planning, bus


@pytest.fixture
def ed():
    return _build()


def _approved_plan(planning, steps, actor="owner"):
    p = planning.draft_plan(actor, "yürütülecek amaç")
    prev = None
    for desc, cap in steps:
        kw = {"requires": [prev]} if prev else {}
        s = planning.add_step(actor, p["id"], desc, capability=cap, **kw)
        prev = s["id"]
    planning.sequence(actor, p["id"])
    planning.mark_approved(actor, p["id"])
    return p["id"]


# ---- ANAYASA: yetkilendirme olmadan yürütme YOK ----
def test_execution_requires_authorization(ed):
    ex, _p, _b = ed
    with pytest.raises(UnauthorizedExecutionError):
        ex.run_capability("owner", "echo", "run")     # authorization boş → reddedilir


def test_authorization_actor(ed):
    ex, _p, _b = ed
    with pytest.raises(UnauthorizedError):
        ex.run_capability("yabanci", "echo", "run", authorization="dec:1")


# ---- INTEGRATION: tek yetenek yürütme + denetim ----
def test_run_capability_success_and_audit(ed):
    ex, _p, bus = ed
    out = ex.run_capability("owner", "echo", "run", {"x": 1}, authorization="decision:42")
    assert out["success"] is True and out["status"] == RunStatus.COMPLETED
    assert ex.explain("owner", out["run_id"])["authorization"] == "decision:42"
    assert any(e["type"] == ExecEvents.CAPABILITY_RUN for e in bus.history())


def test_run_unknown_capability_blocked(ed):
    ex, _p, bus = ed
    out = ex.run_capability("owner", "yok-yetenek", "run", authorization="d:1")
    assert out["success"] is False and out["blocked"] is True and out["status"] == RunStatus.BLOCKED
    assert any(e["type"] == ExecEvents.BLOCKED for e in bus.history())


# ---- ANAYASA: yalnız APPROVED plan yürütülür ----
def test_run_plan_requires_approved(ed):
    ex, planning, _b = ed
    p = planning.draft_plan("owner", "taslak")
    planning.add_step("owner", p["id"], "adım", capability="echo")
    with pytest.raises(UnauthorizedExecutionError):
        ex.run_plan("owner", p["id"])                 # draft → yürütülemez


# ---- INTEGRATION: onaylı plan workflow (sıralı, denetim) ----
def test_run_approved_plan_workflow(ed):
    ex, planning, bus = ed
    pid = _approved_plan(planning, [("hazırla", "echo"), ("gönder", "echo")])
    run = ex.run_plan("owner", pid)
    assert run["status"] == RunStatus.COMPLETED and len(run["steps"]) == 2
    assert all(s["success"] for s in run["steps"])
    types = [e["type"] for e in bus.history()]
    assert ExecEvents.PLAN_RUN_STARTED in types and ExecEvents.PLAN_RUN_FINISHED in types


# ---- INTEGRATION: fail-fast (ilk hatada durur) ----
def test_workflow_fail_fast(ed):
    ex, planning, _b = ed
    pid = _approved_plan(planning, [("ok", "echo"), ("patla", "boom"), ("ulaşılmaz", "echo")])
    run = ex.run_plan("owner", pid)
    assert run["status"] == RunStatus.FAILED
    assert len(run["steps"]) == 2                      # üçüncü adıma ulaşılmadı (fail-fast)
    assert run["steps"][0]["success"] is True and run["steps"][1]["success"] is False


# ---- INTEGRATION: explain/history/stats/contract ----
def test_history_stats_contract(ed):
    ex, _p, _b = ed
    r = ex.run_capability("owner", "echo", "run", authorization="d:1")
    assert any(x["id"] == r["run_id"] for x in ex.history("owner"))
    with pytest.raises(NotFoundError):
        ex.explain("owner", "yok-run")
    s = ex.stats()
    assert s["runs"] >= 1 and s["capability_runs"] >= 1 and s["contract_version"] == "1.0.0"
    c = ex.contract()
    assert c["domain"] == "execution" and "run_plan" in c["operations"]


# ---- SMOKE: boot() → anayasa güvencesi + manuel-adım workflow ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    with pytest.raises(UnauthorizedExecutionError):
        mio.execution.run_capability("owner", "x", "y")            # yetkilendirme yok → reddedilir
    # yeteneksiz (manuel) adımlı onaylı plan → hepsi atlanır, koşu tamamlanır
    p = mio.planning.draft_plan("owner", "manuel akış")
    a = mio.planning.add_step("owner", p["id"], "elle yap 1")
    mio.planning.add_step("owner", p["id"], "elle yap 2", requires=[a["id"]])
    mio.planning.sequence("owner", p["id"])
    mio.planning.mark_approved("owner", p["id"])
    run = mio.execution.run_plan("owner", p["id"])
    assert run["status"] == RunStatus.COMPLETED and all(s.get("skipped") for s in run["steps"])
    assert mio.execution.contract()["version"] == "1.0.0"
    mio.close()
