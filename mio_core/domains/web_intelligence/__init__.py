"""MIO Core · Web Intelligence Domain (bounded context). Public yüzey."""

from .contract import CONTRACT_VERSION, WebEvents, web_contract
from .models import (
    JobStatus,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    WebConfig,
    WebError,
    WebJob,
    WebKind,
    host_of,
)
from .repository import WebRepository
from .service import WebIntelligenceDomain

__all__ = [
    "WebIntelligenceDomain", "WebRepository", "WebJob", "WebKind", "JobStatus", "WebConfig", "host_of",
    "WebError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "WebEvents", "web_contract", "CONTRACT_VERSION",
]
