"""MIO Core · Knowledge Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, KnowEvents, knowledge_contract
from .models import (
    KNOWLEDGE_DOMAINS,
    ImmutableKnowledgeError,
    KnowledgeConfig,
    KnowledgeError,
    KnowledgeItem,
    KnowledgeType,
    LearnCommand,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import KnowledgeRepository
from .service import KnowledgeDomain

__all__ = [
    "KnowledgeDomain", "KnowledgeRepository", "KnowledgeItem", "KnowledgeType", "KnowledgeConfig",
    "LearnCommand", "KNOWLEDGE_DOMAINS",
    "KnowledgeError", "ValidationError", "UnauthorizedError", "NotFoundError", "ImmutableKnowledgeError",
    "KnowEvents", "knowledge_contract", "CONTRACT_VERSION",
]
