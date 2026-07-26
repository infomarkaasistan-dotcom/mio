"""MIO Core · Presentation Domain (bounded context). Public yüzey.

Sunum mantığı (speech/podcast/video/meeting/webinar/livestream/lesson/demo/slides/avatar/conversation). Dış
sistemleri BİLMEZ; yalnız CapabilityIntent üretir. Yürütmeye Executive karar verir (ConnectorManager yalnız
Executive'te)."""

from .contract import CONTRACT_VERSION, PresentationEvents, presentation_contract
from .models import (
    CapabilityIntent,
    HIGH_RISK_INTENTS,
    INTENT_ALIASES,
    Pace,
    PresentationConfig,
    PresentationError,
    NotFoundError,
    ScriptKind,
    Script,
    Segment,
    SegmentKind,
    Session,
    SessionStatus,
    Slide,
    UnauthorizedError,
    ValidationError,
    estimate_seconds,
)
from .repository import PresentationRepository
from .service import PresentationDomain

__all__ = [
    "PresentationDomain", "PresentationRepository", "Script", "Segment", "Slide", "Session",
    "CapabilityIntent", "ScriptKind", "SegmentKind", "Pace", "SessionStatus", "PresentationConfig",
    "HIGH_RISK_INTENTS", "INTENT_ALIASES", "estimate_seconds",
    "PresentationError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "PresentationEvents", "presentation_contract", "CONTRACT_VERSION",
]
