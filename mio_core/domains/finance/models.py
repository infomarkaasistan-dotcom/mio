"""MIO Core · Finance Operations Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Deterministik finans: gelir/gider defteri + nakit akışı/runway + **Financial Rule** (finansal yükümlülük
kullanıcı/Executive onayı olmadan oluşturulamaz — Anayasa Madde 4). Advisory Finance Brain'in operasyonel
karşılığı; hesaplar deterministik, uydurma yok."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TxnKind:
    INCOME = "income"
    EXPENSE = "expense"
    ALL = {INCOME, EXPENSE}


class CommitmentStatus:
    PENDING = "pending_approval"       # Financial Rule: onay bekliyor
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    ALL = {PENDING, APPROVED, REJECTED, EXECUTED}


class FinanceError(Exception):
    """Finance Domain temel hatası."""


class ValidationError(FinanceError):
    pass


class UnauthorizedError(FinanceError):
    pass


class NotFoundError(FinanceError):
    pass


class FinancialRuleError(FinanceError):
    """Financial Rule ihlali (onaysız yükümlülük / geçersiz durum geçişi)."""


@dataclass
class Transaction:
    kind: str
    amount: float
    currency: str = "TRY"
    category: str = "general"
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "amount": self.amount, "currency": self.currency,
                "category": self.category, "description": self.description, "at": self.at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Transaction":
        return cls(kind=d["kind"], amount=float(d["amount"]), currency=d.get("currency", "TRY"),
                   category=d.get("category", "general"), description=d.get("description", ""),
                   id=d.get("id") or uuid4().hex[:12], at=d.get("at") or _now())


@dataclass
class Commitment:
    description: str
    amount: float
    currency: str = "TRY"
    status: str = CommitmentStatus.PENDING
    approved_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "description": self.description, "amount": self.amount,
                "currency": self.currency, "status": self.status, "approved_by": self.approved_by,
                "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Commitment":
        return cls(description=d["description"], amount=float(d["amount"]), currency=d.get("currency", "TRY"),
                   status=d.get("status", CommitmentStatus.PENDING), approved_by=d.get("approved_by", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now())


@dataclass
class FinanceConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Finance", "Operations", "Business", "Planning", "Reasoning"})
    writer_actors: set = field(default_factory=lambda: {"owner", "Executive", "Finance", "Operations"})
    # Financial Rule: yalnız bunlar bir yükümlülüğü onaylayabilir (Madde 4)
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "TxnKind", "CommitmentStatus", "Transaction", "Commitment", "FinanceConfig",
    "FinanceError", "ValidationError", "UnauthorizedError", "NotFoundError", "FinancialRuleError",
]
