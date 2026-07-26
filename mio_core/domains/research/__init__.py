"""MIO Core · Research Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, ResearchEvents, research_contract
from .models import (
    Credibility,
    Finding,
    Inquiry,
    InquiryStatus,
    NotFoundError,
    ResearchConfig,
    ResearchError,
    UnauthorizedError,
    ValidationError,
)
from .repository import ResearchRepository
from .service import ResearchDomain

__all__ = [
    "ResearchDomain", "ResearchRepository", "Inquiry", "Finding", "Credibility", "InquiryStatus",
    "ResearchConfig",
    "ResearchError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "ResearchEvents", "research_contract", "CONTRACT_VERSION",
]
