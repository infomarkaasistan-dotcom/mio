"""MIO Core · Communication Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, CommEvents, communication_contract
from .models import (
    CommunicationConfig,
    CommunicationError,
    Conversation,
    Intent,
    NotFoundError,
    ResponseSource,
    Turn,
    UnauthorizedError,
    ValidationError,
)
from .repository import ConversationRepository
from .service import CommunicationDomain

__all__ = [
    "CommunicationDomain", "ConversationRepository", "Conversation", "Turn", "Intent",
    "ResponseSource", "CommunicationConfig",
    "CommunicationError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "CommEvents", "communication_contract", "CONTRACT_VERSION",
]
