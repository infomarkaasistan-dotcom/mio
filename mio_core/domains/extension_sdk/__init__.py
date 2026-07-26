"""MIO Core · Extension SDK Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, ExtensionEvents, extension_contract
from .models import (
    ExtKind,
    ExtStatus,
    Extension,
    ExtensionConfig,
    ExtensionError,
    NotFoundError,
    TransitionError,
    UnauthorizedError,
    ValidationError,
)
from .repository import ExtensionRepository
from .service import ExtensionSDKDomain

__all__ = [
    "ExtensionSDKDomain", "ExtensionRepository", "Extension", "ExtKind", "ExtStatus", "ExtensionConfig",
    "ExtensionError", "ValidationError", "UnauthorizedError", "NotFoundError", "TransitionError",
    "ExtensionEvents", "extension_contract", "CONTRACT_VERSION",
]
