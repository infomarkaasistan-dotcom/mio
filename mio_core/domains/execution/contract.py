"""MIO Core · Execution Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ExecEvents:
    CAPABILITY_RUN = "execution.capability_run"
    PLAN_RUN_STARTED = "execution.plan_run_started"
    PLAN_RUN_FINISHED = "execution.plan_run_finished"
    STEP_EXECUTED = "execution.step_executed"
    BLOCKED = "execution.blocked"


OPERATIONS = ("run_capability", "run_plan", "history", "explain", "stats")


def execution_contract() -> dict[str, Any]:
    return {
        "domain": "execution",
        "version": CONTRACT_VERSION,
        "description": "Onaylı karar/planı GERÇEK araçlarla (Tool Orchestrator) yürütür; workflow düzeyinde "
                       "denetim izi. Execution ASLA tek başına karar vermez (yetkilendirme zorunlu).",
        "operations": list(OPERATIONS),
        "events": [ExecEvents.CAPABILITY_RUN, ExecEvents.PLAN_RUN_STARTED, ExecEvents.PLAN_RUN_FINISHED,
                   ExecEvents.STEP_EXECUTED, ExecEvents.BLOCKED],
        "run_kinds": ["step", "plan"],
        "invariants": ["yürütme yetkilendirme ister (onaylı plan/karar) — Execution tek başına karar vermez",
                       "yalnız APPROVED plan workflow olarak yürütülür",
                       "her adım denetime yazılır; workflow fail-fast'tir"],
    }
