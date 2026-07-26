"""MIO Core · Sales & CRM Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Deterministik satış operasyonu: contact (lead/customer) + opportunity/pipeline (stage) + ağırlıklı pipeline
metrikleri + lead qualification. Advisory Sales Brain'in operasyonel karşılığı; hesaplar deterministik."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ContactKind:
    LEAD = "lead"
    CUSTOMER = "customer"
    ALL = {LEAD, CUSTOMER}


class Stage:
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"
    ALL = {LEAD, QUALIFIED, PROPOSAL, NEGOTIATION, WON, LOST}
    # Deterministik kazanma olasılığı (ağırlıklı pipeline için)
    PROBABILITY = {LEAD: 0.1, QUALIFIED: 0.3, PROPOSAL: 0.5, NEGOTIATION: 0.7, WON: 1.0, LOST: 0.0}
    OPEN = {LEAD, QUALIFIED, PROPOSAL, NEGOTIATION}


class SalesError(Exception):
    """Sales & CRM Domain temel hatası."""


class ValidationError(SalesError):
    pass


class UnauthorizedError(SalesError):
    pass


class NotFoundError(SalesError):
    pass


@dataclass
class Contact:
    name: str
    kind: str = ContactKind.LEAD
    email: str = ""
    company: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "email": self.email,
                "company": self.company, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Contact":
        return cls(name=d["name"], kind=d.get("kind", ContactKind.LEAD), email=d.get("email", ""),
                   company=d.get("company", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class Opportunity:
    contact_id: str
    title: str
    value: float = 0.0
    currency: str = "TRY"
    stage: str = Stage.LEAD
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "contact_id": self.contact_id, "title": self.title, "value": self.value,
                "currency": self.currency, "stage": self.stage, "weighted_value": round(
                    self.value * Stage.PROBABILITY.get(self.stage, 0.0), 2),
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Opportunity":
        return cls(contact_id=d["contact_id"], title=d["title"], value=float(d.get("value", 0.0)),
                   currency=d.get("currency", "TRY"), stage=d.get("stage", Stage.LEAD),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   updated_at=d.get("updated_at") or _now())


@dataclass
class SalesConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Sales", "Marketing", "Operations", "Business", "Planning", "Reasoning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Sales", "Operations"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "ContactKind", "Stage", "Contact", "Opportunity", "SalesConfig",
    "SalesError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
