"""MIO Core · Customer Success Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, CSEvents, customer_contract
from .models import (
    Account,
    CSConfig,
    CSError,
    Feedback,
    NotFoundError,
    Priority,
    Ticket,
    TicketStatus,
    UnauthorizedError,
    ValidationError,
)
from .repository import CustomerRepository
from .service import CustomerSuccessDomain

__all__ = [
    "CustomerSuccessDomain", "CustomerRepository", "Account", "Ticket", "Feedback", "Priority",
    "TicketStatus", "CSConfig",
    "CSError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "CSEvents", "customer_contract", "CONTRACT_VERSION",
]
