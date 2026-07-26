"""MIO Core · Goal Management Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class GoalMgmtEvents:
    GOAL_DEFINED = "goal_management.goal_defined"
    MILESTONE_ADDED = "goal_management.milestone_added"
    TASK_ADDED = "goal_management.task_added"
    TASK_RESULT = "goal_management.task_result"
    GOAL_COMPLETED = "goal_management.goal_completed"
    GOAL_ABANDONED = "goal_management.goal_abandoned"


OPERATIONS = ("define_goal", "add_milestone", "add_task", "record_result", "abandon",
              "tree", "progress", "list_goals", "stats")


def goal_management_contract() -> dict[str, Any]:
    return {
        "domain": "goal_management",
        "version": CONTRACT_VERSION,
        "description": "Uzun-vadeli hedef hiyerarşisi (hedef→milestone→görev) yönetimi, deterministik "
                       "ilerleme ve E1 senkron. LLM'den bağımsız.",
        "operations": list(OPERATIONS),
        "events": [GoalMgmtEvents.GOAL_DEFINED, GoalMgmtEvents.MILESTONE_ADDED, GoalMgmtEvents.TASK_ADDED,
                   GoalMgmtEvents.TASK_RESULT, GoalMgmtEvents.GOAL_COMPLETED, GoalMgmtEvents.GOAL_ABANDONED],
        "hierarchy": ["goal", "milestone", "task"],
        "invariants": ["ilerleme deterministiktir (tamamlanan görev oranı)",
                       "milestone tüm görevleri bitince tamamlanır; hedef tüm milestone'lar bitince tamamlanır",
                       "aktif hedef indeksi E1 ile senkron (meşru vazgeçiş desteklenir)"],
    }
