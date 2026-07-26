"""MIO Core · Conversation Domain (bounded context). Public yüzey.

Gerçek zamanlı etkileşim mantığı (mesaj/moderasyon/öncelik/sıra/özet). Platformları BİLMEZ; yalnız
CapabilityIntent üretir. Moderasyon KARAR VERMEZ (Executive'e öneri). Yürütmeye Executive karar verir."""

from .contract import CONTRACT_VERSION, ConversationEvents, conversation_contract
from .models import (
    ConversationConfig,
    ConversationError,
    ConversationIntent,
    HIGH_RISK_CONV_INTENTS,
    Message,
    MessageIntent,
    Moderation,
    ModerationFlag,
    NotFoundError,
    Priority,
    SessionStatus,
    UnauthorizedError,
    UserProfile,
    ValidationError,
    classify_intent,
    moderate_text,
)
from .repository import ConversationRepository
from .service import ConversationDomain

__all__ = [
    "ConversationDomain", "ConversationRepository", "Message", "UserProfile", "Moderation",
    "ConversationIntent", "MessageIntent", "Priority", "ModerationFlag", "SessionStatus",
    "ConversationConfig", "HIGH_RISK_CONV_INTENTS", "classify_intent", "moderate_text",
    "ConversationError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "ConversationEvents", "conversation_contract", "CONTRACT_VERSION",
]
