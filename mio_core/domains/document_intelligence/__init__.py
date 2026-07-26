"""MIO Core · Document Intelligence Domain (bounded context). Public yüzey."""

from . import analyzer
from .contract import CONTRACT_VERSION, DocEvents, document_contract
from .models import (
    DocConfig,
    DocType,
    Document,
    DocumentError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import DocumentRepository
from .service import DocumentIntelligenceDomain

__all__ = [
    "DocumentIntelligenceDomain", "DocumentRepository", "Document", "DocType", "DocConfig", "analyzer",
    "DocumentError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "DocEvents", "document_contract", "CONTRACT_VERSION",
]
