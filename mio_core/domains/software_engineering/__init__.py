"""MIO Core · Software Engineering Domain (bounded context). Public yüzey."""

from .analyzer import analyze
from .contract import CONTRACT_VERSION, SEEvents, software_contract
from .models import (
    Artifact,
    EngTask,
    NotFoundError,
    SEConfig,
    SEError,
    TaskKind,
    TaskStatus,
    UnauthorizedError,
    ValidationError,
)
from .repository import SoftwareRepository
from .service import SoftwareEngineeringDomain

__all__ = [
    "SoftwareEngineeringDomain", "SoftwareRepository", "Artifact", "EngTask", "TaskKind", "TaskStatus",
    "SEConfig", "analyze",
    "SEError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "SEEvents", "software_contract", "CONTRACT_VERSION",
]
