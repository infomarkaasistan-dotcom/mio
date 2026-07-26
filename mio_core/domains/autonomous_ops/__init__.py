"""MIO Core · Autonomous Operations Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, AutoOpsEvents, auto_ops_contract
from .models import (
    AutoOpsConfig,
    AutoOpsError,
    NotFoundError,
    OpsRule,
    Proposal,
    ProposalStatus,
    Severity,
    UnauthorizedError,
    ValidationError,
)
from .repository import AutoOpsRepository
from .service import AutonomousOperationsDomain

__all__ = [
    "AutonomousOperationsDomain", "AutoOpsRepository", "OpsRule", "Proposal", "ProposalStatus", "Severity",
    "AutoOpsConfig",
    "AutoOpsError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "AutoOpsEvents", "auto_ops_contract", "CONTRACT_VERSION",
]
