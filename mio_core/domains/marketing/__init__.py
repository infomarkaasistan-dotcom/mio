"""MIO Core · Marketing & Growth Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, MarketingEvents, marketing_contract
from .models import (
    Campaign,
    CampaignStatus,
    MarketingConfig,
    MarketingError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import MarketingRepository
from .service import MarketingDomain

__all__ = [
    "MarketingDomain", "MarketingRepository", "Campaign", "CampaignStatus", "MarketingConfig",
    "MarketingError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "MarketingEvents", "marketing_contract", "CONTRACT_VERSION",
]
