"""MIO Core · Knowledge Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Tipli bilgi (Belief/Rule/Concept/Pattern/Principle/MentalModel/ReasoningTemplate/DecisionHeuristic)
yönetimi için bounded context. Çekirdek `KnowledgeItem`/`KnowledgeType` yeniden kullanılır (çoğaltma yok);
bu modül governance kabuğunu (hata hiyerarşisi, config, köken/authorization kuralları) ekler.

Innate bilgi (source="innate") DOKTRİNERDİR: budanamaz, silinemez. Yaşayan bilgi (learned:*) governance
altında öğrenilir, güç kazanır/kaybeder ve gerektiğinde unutulur."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Çekirdek tipli-bilgi yapıları yeniden kullanılır — Knowledge Domain onları SARAR, kopyalamaz.
from mio_core.knowledge import KnowledgeBase, KnowledgeItem, KnowledgeType, KNOWLEDGE_DOMAINS

__all__ = [
    "KnowledgeItem", "KnowledgeType", "KnowledgeBase", "KNOWLEDGE_DOMAINS",
    "KnowledgeConfig", "LearnCommand",
    "KnowledgeError", "ValidationError", "UnauthorizedError", "NotFoundError", "ImmutableKnowledgeError",
    "INNATE_SOURCE", "learned_source",
]

INNATE_SOURCE = "innate"


def learned_source(actor: str) -> str:
    """Yaşayan bilginin kökenini (provenance) aktörle işaretler."""
    return f"learned:{actor}"


def is_innate(item: KnowledgeItem) -> bool:
    return (item.source or "").strip().lower() == INNATE_SOURCE


class KnowledgeError(Exception):
    """Knowledge Domain temel hatası."""


class ValidationError(KnowledgeError):
    pass


class UnauthorizedError(KnowledgeError):
    pass


class NotFoundError(KnowledgeError):
    pass


class ImmutableKnowledgeError(KnowledgeError):
    """Innate (doktriner) bilgi değiştirilemez/silinemez."""


@dataclass
class LearnCommand:
    """Yaşayan bilgi öğrenme isteği (yapılandırılmış)."""
    ktype: str
    name: str
    statement: str = ""
    domain: str = "general"
    when: list[str] = field(default_factory=list)
    then: str = ""
    steps: list[str] = field(default_factory=list)
    confidence: float = 0.7
    tags: list[str] = field(default_factory=list)


@dataclass
class KnowledgeConfig:
    reinforce_step: float = 0.05                 # varsayılan güven revizyon adımı
    min_confidence: float = 0.05                 # yaşayan bilgi bu güvenin altına düşerse aday-unutma
    applicable_types: frozenset = frozenset({KnowledgeType.RULE, KnowledgeType.PATTERN,
                                             KnowledgeType.DECISION_HEURISTIC})
    # Tüm okuma/uygulama işlemleri için yetkili aktörler
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Knowledge", "Learning", "Reasoning", "Planning", "Memory"})
    # Yazma (learn/reinforce/forget) yalnızca bu aktörlere açık
    writer_actors: set = field(default_factory=lambda: {"owner", "Knowledge", "Learning"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def valid_domain(self, domain: Optional[str]) -> bool:
        return domain is None or domain == "general" or domain in KNOWLEDGE_DOMAINS
