"""MIO Core · Execution Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, ExecEvents, execution_contract
from .models import (
    ExecutionConfig,
    ExecutionError,
    ExecutionRun,
    NotFoundError,
    RunKind,
    RunStatus,
    UnauthorizedError,
    UnauthorizedExecutionError,
    ValidationError,
)
from .repository import ExecutionRepository
from .service import ExecutionDomain

__all__ = [
    "ExecutionDomain", "ExecutionRepository", "ExecutionRun", "RunKind", "RunStatus", "ExecutionConfig",
    "ExecutionError", "ValidationError", "UnauthorizedError", "NotFoundError", "UnauthorizedExecutionError",
    "ExecEvents", "execution_contract", "CONTRACT_VERSION",
]
