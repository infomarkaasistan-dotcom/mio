"""MIO Core · Customer Success Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Deterministik müşteri başarısı: account + support ticket (öncelik/durum) + CSAT (1-5) + deterministik health
score + churn-risk bayrağı. Advisory değil, operasyonel; hesaplar deterministik (uydurma yok)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Priority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ALL = {LOW, MEDIUM, HIGH}
    WEIGHT = {LOW: 3, MEDIUM: 7, HIGH: 15}   # açık ticket'ın health'e negatif etkisi


class TicketStatus:
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ALL = {OPEN, IN_PROGRESS, RESOLVED}
    ACTIVE = {OPEN, IN_PROGRESS}             # health'i etkileyen "açık" durumlar


class CSError(Exception):
    """Customer Success Domain temel hatası."""


class ValidationError(CSError):
    pass


class UnauthorizedError(CSError):
    pass


class NotFoundError(CSError):
    pass


@dataclass
class Account:
    name: str
    tier: str = "standard"
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "tier": self.tier, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Account":
        return cls(name=d["name"], tier=d.get("tier", "standard"), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class Ticket:
    account_id: str
    subject: str
    priority: str = Priority.MEDIUM
    status: str = TicketStatus.OPEN
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "account_id": self.account_id, "subject": self.subject,
                "priority": self.priority, "status": self.status, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Ticket":
        return cls(account_id=d["account_id"], subject=d["subject"],
                   priority=d.get("priority", Priority.MEDIUM), status=d.get("status", TicketStatus.OPEN),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now())


@dataclass
class Feedback:
    account_id: str
    score: int                              # CSAT 1-5
    comment: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "account_id": self.account_id, "score": self.score,
                "comment": self.comment, "at": self.at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Feedback":
        return cls(account_id=d["account_id"], score=int(d["score"]), comment=d.get("comment", ""),
                   id=d.get("id") or uuid4().hex[:12], at=d.get("at") or _now())


@dataclass
class CSConfig:
    churn_risk_below: float = 50.0          # health bu değerin altındaysa churn riski
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "CustomerSuccess", "Sales", "Operations", "Business", "Planning", "Reasoning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "CustomerSuccess", "Operations"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "Priority", "TicketStatus", "Account", "Ticket", "Feedback", "CSConfig",
    "CSError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
