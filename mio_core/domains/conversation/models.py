"""MIO Core · Conversation Domain — modeller, config (production-grade), LLM-BAĞIMSIZ, DETERMİNİSTİK.

**Gerçek zamanlı insan etkileşiminin MANTIĞINI bilir; platformları (YouTube/Discord/Slack/Telegram/Teams/Twitch/
Kick/Instagram/WhatsApp) İSİM olarak bile bilmez.** Mesaj alma/sınıflandırma, niyet analizi, bağlam, spam/flood/
hakaret tespiti, öncelik (VIP), moderasyon, sıra yönetimi, konu takibi, özet.

**KATMAN AYRIMI (değişmez):** Domain ConnectorManager'ı/connector'ı ASLA çağırmaz; doğrudan cevap GÖNDEREMEZ.
Yalnız **CapabilityIntent** (soyut niyet: conversation.reply/delete/ban...) üretir. **Moderasyon: tespit eder,
KARAR VERMEZ** — Executive'e öneri sunar (sil/engelle/cevapla/yoksay Executive'in). Yüksek-risk niyet onay ister
(Madde 24). Öğrenme yapmaz (Learning'e sinyal gönderilebilir)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MessageIntent:
    QUESTION = "question"
    STATEMENT = "statement"
    COMMAND = "command"
    GREETING = "greeting"
    FEEDBACK = "feedback"
    ALL = {QUESTION, STATEMENT, COMMAND, GREETING, FEEDBACK}


class Priority:
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    VIP = "vip"
    ORDER = {LOW: 0, NORMAL: 1, HIGH: 2, VIP: 3}


class ModerationFlag:
    SPAM = "spam"
    FLOOD = "flood"
    ABUSE = "abuse"       # hakaret/küfür
    AD = "ad"             # reklam/link
    CLEAN = "clean"


class SessionStatus:
    OPEN = "open"
    ESCALATED = "escalated"
    CLOSED = "closed"
    ALL = {OPEN, ESCALATED, CLOSED}


# Yüksek-risk conversation niyetleri (moderasyon/kitle) → Executive ONAY ister (Madde 24).
# capability İSİMLERİ (paylaşılan protokol) — domain connector katmanını import ETMEZ.
HIGH_RISK_CONV_INTENTS = frozenset({
    "conversation.delete", "conversation.timeout", "conversation.ban", "conversation.broadcast",
    "conversation.pin",
})

# Deterministik moderasyon sözlükleri (üretimde config'ten genişletilebilir).
_ABUSE_WORDS = ("aptal", "salak", "gerizekalı", "idiot", "stupid", "moron", "orospu", "piç")
_AD_MARKERS = ("http://", "https://", "www.", "discount", "buy now", "promo", "kazanç", "bedava para",
               "telegram.me", "t.me/")


class ConversationError(Exception):
    """Conversation Domain temel hatası."""


class ValidationError(ConversationError):
    pass


class UnauthorizedError(ConversationError):
    pass


class NotFoundError(ConversationError):
    pass


def classify_intent(text: str) -> str:
    """Deterministik niyet sınıflandırma (LLM'siz; keyword/pattern)."""
    t = (text or "").strip().lower()
    if not t:
        return MessageIntent.STATEMENT
    if t.endswith("?") or t.split()[0] in ("ne", "nasıl", "neden", "nerede", "kim", "ne zaman",
                                           "what", "how", "why", "where", "who", "when", "mı", "mi"):
        return MessageIntent.QUESTION
    if t.startswith(("/", "!")) or t.split()[0] in ("başlat", "durdur", "aç", "kapat", "start", "stop"):
        return MessageIntent.COMMAND
    if t in ("selam", "merhaba", "hi", "hello", "hey", "günaydın"):
        return MessageIntent.GREETING
    if any(w in t for w in ("teşekkür", "harika", "kötü", "beğendim", "thanks", "great", "bad")):
        return MessageIntent.FEEDBACK
    return MessageIntent.STATEMENT


@dataclass
class UserProfile:
    handle: str
    vip: bool = False
    message_count: int = 0
    warnings: int = 0
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    first_seen: str = field(default_factory=_now)
    last_texts: list = field(default_factory=list)   # son mesajlar (flood/tekrar tespiti)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "handle": self.handle, "vip": self.vip,
                "message_count": self.message_count, "warnings": self.warnings, "first_seen": self.first_seen}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "UserProfile":
        return cls(handle=d["handle"], vip=bool(d.get("vip", False)),
                   message_count=int(d.get("message_count", 0)), warnings=int(d.get("warnings", 0)),
                   id=d.get("id") or uuid4().hex[:12], first_seen=d.get("first_seen") or _now(),
                   last_texts=list(d.get("last_texts") or []))


@dataclass
class Moderation:
    flags: list = field(default_factory=list)        # ModerationFlag
    severity: str = "none"                           # none | low | high
    recommendation: str = "allow"                    # allow | reply | ignore | delete | timeout | ban
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"flags": list(self.flags), "severity": self.severity,
                "recommendation": self.recommendation, "requires_approval": self.requires_approval}


@dataclass
class Message:
    user_handle: str
    text: str
    platform_ref: dict = field(default_factory=dict)  # opak (domain platformu bilmez; connector çözer)
    intent: str = MessageIntent.STATEMENT
    priority: str = Priority.NORMAL
    moderation: dict = field(default_factory=dict)
    answered: bool = False
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "user_handle": self.user_handle, "text": self.text,
                "platform_ref": dict(self.platform_ref), "intent": self.intent, "priority": self.priority,
                "moderation": dict(self.moderation), "answered": self.answered, "ts": self.ts}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Message":
        return cls(user_handle=d["user_handle"], text=d["text"], platform_ref=dict(d.get("platform_ref") or {}),
                   intent=d.get("intent", MessageIntent.STATEMENT), priority=d.get("priority", Priority.NORMAL),
                   moderation=dict(d.get("moderation") or {}), answered=bool(d.get("answered", False)),
                   id=d.get("id") or uuid4().hex[:12], ts=d.get("ts") or _now())


@dataclass
class ConversationIntent:
    """Domain'in ürettiği NİYET (yürütme DEĞİL). Executive ConnectorManager ile yürütür (ya da yürütmez)."""
    capability: str
    request: dict = field(default_factory=dict)
    label: str = ""
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"capability": self.capability, "request": dict(self.request), "label": self.label,
                "requires_approval": self.requires_approval}


@dataclass
class ConversationConfig:
    flood_window: int = 5                            # son N mesaj penceresi
    flood_threshold: int = 4                         # bu pencerede aynı kullanıcıdan ≥ eşik → flood
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Communication", "Moderation", "Marketing"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Communication", "Moderation"})
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


def moderate_text(text: str, *, repeats: int = 0, flood: bool = False) -> Moderation:
    """DETERMİNİSTİK moderasyon TESPİTİ (karar DEĞİL — öneri). spam/flood/abuse/ad tespit eder."""
    t = (text or "").lower()
    flags: list = []
    if flood:
        flags.append(ModerationFlag.FLOOD)
    if repeats >= 2:
        flags.append(ModerationFlag.SPAM)
    if any(w in t for w in _ABUSE_WORDS):
        flags.append(ModerationFlag.ABUSE)
    if any(m in t for m in _AD_MARKERS):
        flags.append(ModerationFlag.AD)
    if not flags:
        return Moderation(flags=[ModerationFlag.CLEAN], severity="none", recommendation="allow")
    # şiddet + öneri (Executive'e; domain KARAR VERMEZ)
    if ModerationFlag.ABUSE in flags or (ModerationFlag.FLOOD in flags and ModerationFlag.SPAM in flags):
        return Moderation(flags=flags, severity="high", recommendation="timeout", requires_approval=True)
    if ModerationFlag.SPAM in flags or ModerationFlag.AD in flags:
        return Moderation(flags=flags, severity="high", recommendation="delete", requires_approval=True)
    return Moderation(flags=flags, severity="low", recommendation="ignore", requires_approval=False)


__all__ = [
    "MessageIntent", "Priority", "ModerationFlag", "SessionStatus", "HIGH_RISK_CONV_INTENTS",
    "classify_intent", "moderate_text", "UserProfile", "Message", "Moderation", "ConversationIntent",
    "ConversationConfig", "ConversationError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
