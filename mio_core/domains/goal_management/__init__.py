"""MIO Core · Goal Management Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, GoalMgmtEvents, goal_management_contract
from .models import (
    GoalConfig,
    GoalError,
    GoalTask,
    LongTermGoal,
    Milestone,
    NotFoundError,
    TASK_RESULT_STATUSES,
    UnauthorizedError,
    ValidationError,
)
from .service import GoalManagementDomain

__all__ = [
    "GoalManagementDomain", "GoalConfig", "LongTermGoal", "Milestone", "GoalTask",
    "TASK_RESULT_STATUSES",
    "GoalError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "GoalMgmtEvents", "goal_management_contract", "CONTRACT_VERSION",
]
