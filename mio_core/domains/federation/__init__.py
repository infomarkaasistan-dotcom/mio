"""MIO Core · Federation Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, FederationEvents, federation_contract
from .models import (
    FederationConfig,
    FederationError,
    NotFoundError,
    Peer,
    PeerStatus,
    ShareJob,
    ShareStatus,
    TransitionError,
    TrustLevel,
    UnauthorizedError,
    ValidationError,
)
from .repository import FederationRepository
from .service import FederationDomain

__all__ = [
    "FederationDomain", "FederationRepository", "Peer", "ShareJob", "PeerStatus", "ShareStatus", "TrustLevel",
    "FederationConfig",
    "FederationError", "ValidationError", "UnauthorizedError", "NotFoundError", "TransitionError",
    "FederationEvents", "federation_contract", "CONTRACT_VERSION",
]
