"""MIO Core · Executive Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, ExecEvents, executive_contract
from .models import (
    DecisionCommand,
    DecisionOutcome,
    ExecutiveConfig,
    ExecutiveError,
    GoalOutcome,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .service import ExecutiveDomain

__all__ = [
    "ExecutiveDomain", "ExecutiveConfig", "DecisionCommand", "DecisionOutcome", "GoalOutcome",
    "ExecutiveError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "ExecEvents", "executive_contract", "CONTRACT_VERSION",
]
