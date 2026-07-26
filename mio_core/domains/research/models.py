"""MIO Core · Research Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Deterministik araştırma: soruşturma (inquiry) + bulgu (finding; kaynak/güvenilirlik/provenance) + DETERMİNİSTİK
sentez (corroboration sayımı, tek-kaynak/doğrulanmamış bayrağı). LLM prose-sentezi danışmandır; yapısal sentez
ve doğrulama deterministiktir (uydurma yok — yalnız girilen bulgulardan)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Credibility:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    WEIGHT = {LOW: 0.3, MEDIUM: 0.6, HIGH: 0.9}
    ALL = set(WEIGHT)


class InquiryStatus:
    OPEN = "open"
    SYNTHESIZED = "synthesized"
    CLOSED = "closed"
    ALL = {OPEN, SYNTHESIZED, CLOSED}


class ResearchError(Exception):
    """Research Domain temel hatası."""


class ValidationError(ResearchError):
    pass


class UnauthorizedError(ResearchError):
    pass


class NotFoundError(ResearchError):
    pass


@dataclass
class Inquiry:
    question: str
    status: str = InquiryStatus.OPEN
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "question": self.question, "status": self.status,
                "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Inquiry":
        return cls(question=d["question"], status=d.get("status", InquiryStatus.OPEN),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now())


@dataclass
class Finding:
    inquiry_id: str
    statement: str
    source: str = ""
    credibility: str = Credibility.MEDIUM
    verified: bool = False
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "inquiry_id": self.inquiry_id, "statement": self.statement,
                "source": self.source, "credibility": self.credibility, "verified": self.verified,
                "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Finding":
        return cls(inquiry_id=d["inquiry_id"], statement=d["statement"], source=d.get("source", ""),
                   credibility=d.get("credibility", Credibility.MEDIUM), verified=bool(d.get("verified", False)),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now())


@dataclass
class ResearchConfig:
    corroboration_min: int = 2         # bu kadar DİSTİNCT kaynak → doğrulanmış (corroborated)
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Research", "Knowledge", "Reasoning", "Planning", "Marketing", "Operations"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Research", "Knowledge", "Operations"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "Credibility", "InquiryStatus", "Inquiry", "Finding", "ResearchConfig",
    "ResearchError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
