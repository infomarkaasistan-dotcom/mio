"""MIO Core · Sales & CRM Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, SalesEvents, sales_contract
from .models import (
    Contact,
    ContactKind,
    NotFoundError,
    Opportunity,
    SalesConfig,
    SalesError,
    Stage,
    UnauthorizedError,
    ValidationError,
)
from .repository import SalesRepository
from .service import SalesCRMDomain

__all__ = [
    "SalesCRMDomain", "SalesRepository", "Contact", "Opportunity", "ContactKind", "Stage", "SalesConfig",
    "SalesError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "SalesEvents", "sales_contract", "CONTRACT_VERSION",
]
