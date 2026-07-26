"""MIO Core · Vertical Domain Brains — modeller, spec'ler, config (production-grade), LLM-BAĞIMSIZ.

8 dikey alan beyni (Business/Finance/Marketing/Sales/Product/Engineering/Security/Operations) ortak bir
çekirdeği (`VerticalBrain`) paylaşır; her biri KENDİ alan bilgisi, odak bağlamı ve GUARDRAIL kurallarıyla
farklılaşır. Hepsi TAVSİYE üretir — **karar VERMEZLER** (kararlar Executive/E4'e aittir). Guardrail'ler
Anayasa'yı deterministik uygular (Finance = Financial Rule; Security/Engineering = geri-alınamaz koruma)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GateVerdict:
    ALLOW = "allow"
    NEEDS_APPROVAL = "needs_approval"     # kullanıcı/Executive onayı gerekir (onayla bypass edilebilir)
    DENY = "deny"                         # sert red (bypass edilemez)


class VerticalError(Exception):
    """Vertical Domain Brain temel hatası."""


class ValidationError(VerticalError):
    pass


class UnauthorizedError(VerticalError):
    pass


class NotFoundError(VerticalError):
    pass


@dataclass(frozen=True)
class VerticalSpec:
    """Bir dikey alan beyninin bildirimsel tanımı (davranış farkı KODda değil VERİDE)."""
    name: str                            # "finance"
    title: str                           # "Finance Brain"
    primary_domain: str                  # Knowledge alanı (ör. "finance")
    focus_tags: tuple[str, ...] = ()     # advise'ta bağlama eklenen odak etiketleri (innate kuralları tetikler)
    gates: tuple[tuple[str, str, str], ...] = ()   # (trigger_tag, GateVerdict, reason) — guardrail'ler


# 8 dikey beyin — davranış farkı yalnız bu spec'lerde (odak bilgi alanı + guardrail'ler).
VERTICAL_SPECS: tuple[VerticalSpec, ...] = (
    VerticalSpec("business", "Business Brain", "business",
                 focus_tags=(), gates=()),
    VerticalSpec("finance", "Finance Brain", "finance",
                 focus_tags=("new_expense",),
                 gates=(("financial_commitment", GateVerdict.NEEDS_APPROVAL,
                         "Financial Rule: kullanıcı onayı olmadan finansal yükümlülük oluşturulamaz."),
                        ("new_expense", GateVerdict.NEEDS_APPROVAL,
                         "Önce ücretsiz/mevcut alternatif araştırılmalı (para harcamak çözüm değildir)."))),
    VerticalSpec("marketing", "Marketing Brain", "marketing",
                 focus_tags=(), gates=()),
    VerticalSpec("sales", "Sales Brain", "sales",
                 focus_tags=("cold_lead",), gates=()),
    VerticalSpec("product", "Product Brain", "product",
                 focus_tags=(), gates=()),
    VerticalSpec("engineering", "Engineering Brain", "software_engineering",
                 focus_tags=("repetitive_task",),
                 gates=(("irreversible_action", GateVerdict.NEEDS_APPROVAL,
                         "Riskli/geri-alınamaz işlem: önce yedek + Executive onayı."),)),
    VerticalSpec("security", "Security Brain", "security",
                 focus_tags=("irreversible_action",),
                 gates=(("irreversible_action", GateVerdict.NEEDS_APPROVAL,
                         "Geri-alınamaz/dış aksiyon: Executive onayı + geri-alınabilirlik değerlendirmesi gerekir."),)),
    VerticalSpec("operations", "Operations Brain", "systems_thinking",
                 focus_tags=("repetitive_task",), gates=()),
)

VERTICAL_BY_NAME = {s.name: s for s in VERTICAL_SPECS}


@dataclass
class Advice:
    """Bir dikey beynin ürettiği TAVSİYE (karar değil)."""
    brain: str
    task: str
    recommendation: str = ""
    confidence: float = 0.0
    considerations: list[dict[str, Any]] = field(default_factory=list)
    context_tags: list[str] = field(default_factory=list)
    decision_authority: str = "Executive"       # karar mercii — dikey beyin karar VERMEZ
    actor: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:16])
    at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "brain": self.brain, "task": self.task,
                "recommendation": self.recommendation, "confidence": self.confidence,
                "considerations": self.considerations, "context_tags": list(self.context_tags),
                "decision_authority": self.decision_authority, "actor": self.actor, "at": self.at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Advice":
        return cls(brain=d["brain"], task=d["task"], recommendation=d.get("recommendation", ""),
                   confidence=float(d.get("confidence", 0.0)),
                   considerations=list(d.get("considerations") or []),
                   context_tags=list(d.get("context_tags") or []),
                   decision_authority=d.get("decision_authority", "Executive"),
                   actor=d.get("actor", ""), id=d.get("id") or uuid4().hex[:16], at=d.get("at") or _now())


@dataclass
class VerticalConfig:
    reader_actor: str = "Reasoning"      # Knowledge/Reasoning'e karşı yetkili okuyucu kimliği
    history_limit: int = 100
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Planning", "Reasoning", "Communication",
        "Business", "Finance", "Marketing", "Sales", "Product", "Engineering", "Security", "Operations"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors


__all__ = [
    "VerticalSpec", "VERTICAL_SPECS", "VERTICAL_BY_NAME", "Advice", "VerticalConfig", "GateVerdict",
    "VerticalError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
