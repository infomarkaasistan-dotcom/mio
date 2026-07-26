"""MIO Core · Communication Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Diyalog yüzeyi: çok-turlu, kalıcı konuşmalar + DETERMİNİSTİK niyet sınıflandırma + yanıt kompozisyonu.
LLM YALNIZCA opsiyonel bir DANIŞMANDIR (doğal ifade için) — erişilemezse domain deterministik yollarla
(kayıtlı handler / dürüst geri-dönüş) çalışmaya devam eder. Communication KARAR VERMEZ; niyeti çekirdeğe
yönlendirir, cevabı derler."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Intent:
    GREETING = "greeting"
    STATUS = "status"                 # kimsin / ne yapabilirsin / durumun
    QUERY_KNOWLEDGE = "query_knowledge"
    GOAL = "goal"
    PLAN = "plan"
    REASON = "reason"
    UNKNOWN = "unknown"
    ALL = {GREETING, STATUS, QUERY_KNOWLEDGE, GOAL, PLAN, REASON, UNKNOWN}


# Deterministik sınıflandırma anahtarları (sıralı; ilk eşleşen kazanır). Türkçe küçük-harf.
INTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (Intent.GREETING, ("merhaba", "selam", "günaydın", "gunaydin", "iyi akşam", "hey ", "naber")),
    (Intent.STATUS, ("kimsin", "kim sin", "ne yapabilir", "neler yapabilir", "yeteneğin", "yetenekler",
                     "durumun", "kendini tanıt", "nesin")),
    (Intent.QUERY_KNOWLEDGE, ("ne biliyorsun", "biliyor musun", "nedir", "ne demek", "hakkında",
                              "bilgi ver", "anlat", "açıkla")),
    (Intent.PLAN, ("plan", "adım adım", "yol harita", "nasıl yapar")),
    (Intent.GOAL, ("hedef", "amaç", "gaye")),
    (Intent.REASON, ("karar", "değerlendir", "düşün", "gerekçe", "mantık")),
)


class ResponseSource:
    HANDLER = "handler"               # deterministik çekirdek handler'ı
    ADVISOR = "advisor"               # LLM danışman (opsiyonel)
    FALLBACK = "fallback"             # dürüst geri-dönüş (yanıtlayamıyorum)


class CommunicationError(Exception):
    """Communication Domain temel hatası."""


class ValidationError(CommunicationError):
    pass


class UnauthorizedError(CommunicationError):
    pass


class NotFoundError(CommunicationError):
    pass


@dataclass
class Turn:
    role: str                          # user | assistant
    text: str
    intent: str = ""
    source: str = ""
    at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "text": self.text, "intent": self.intent,
                "source": self.source, "at": self.at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Turn":
        return cls(role=d["role"], text=d["text"], intent=d.get("intent", ""),
                   source=d.get("source", ""), at=d.get("at") or _now())


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: uuid4().hex[:16])
    turns: list[Turn] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def add(self, turn: Turn) -> None:
        self.turns.append(turn)
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "turns": [t.to_dict() for t in self.turns],
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Conversation":
        return cls(id=d.get("id") or uuid4().hex[:16],
                   turns=[Turn.from_dict(t) for t in d.get("turns") or []],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now())


@dataclass
class CommunicationConfig:
    max_turns: int = 500
    identity_actor: str = "Communication"
    authorized_actors: set = field(default_factory=lambda: {"owner", "Communication", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors


__all__ = [
    "Intent", "INTENT_KEYWORDS", "ResponseSource", "Turn", "Conversation", "CommunicationConfig",
    "CommunicationError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
