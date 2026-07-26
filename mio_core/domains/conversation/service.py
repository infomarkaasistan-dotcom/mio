"""MIO Core · Conversation Domain Service (production-grade), LLM-BAĞIMSIZ, DETERMİNİSTİK.

Gerçek zamanlı etkileşim mantığı: mesaj alma/sınıflandırma, öncelik (VIP), spam/flood/hakaret TESPİTİ, moderasyon
ÖNERİSİ, sıra, özet. **Domain ConnectorManager'ı çağırmaz; doğrudan cevap göndermez** — yalnız CapabilityIntent
üretir. Moderasyon KARAR VERMEZ (Executive'e öneri). Yüksek-risk niyet onay ister (Madde 24). authz · validation ·
events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, ConversationEvents, conversation_contract
from .models import (
    ConversationConfig,
    ConversationIntent,
    HIGH_RISK_CONV_INTENTS,
    Message,
    ModerationFlag,
    NotFoundError,
    Priority,
    UnauthorizedError,
    UserProfile,
    ValidationError,
    classify_intent,
    moderate_text,
)
from .repository import ConversationRepository

logger = logging.getLogger("mio.domain.conversation")


class ConversationDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: ConversationRepository, *, bus=None,
                 config: Optional[ConversationConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or ConversationConfig()
        self._metrics = {"received": 0, "spam": 0, "abuse": 0, "escalated": 0, "replies_planned": 0,
                         "high_risk_intents": 0}

    # -- mesaj alma + işleme (deterministik) ---------------------------- #
    def receive(self, actor: str, user_handle: str, text: str, *,
                platform_ref: Optional[dict] = None) -> dict[str, Any]:
        """Mesaj alır: kullanıcı profili + sınıflandırma + öncelik + moderasyon TESPİTİ. Cevap GÖNDERMEZ."""
        self._authorize_writer(actor)
        user_handle = self._require(user_handle, "kullanıcı")
        text = text if text is not None else ""

        user = self._repo.get_user(user_handle)
        first_time = user is None
        if user is None:
            user = UserProfile(handle=user_handle)
        user.message_count += 1

        # flood/tekrar tespiti (deterministik, kullanıcı geçmişinden)
        recent = user.last_texts[-self._cfg.flood_window:]
        repeats = recent.count(text)
        flood = len(recent) >= self._cfg.flood_threshold and len(set(recent + [text])) <= 2
        user.last_texts = (user.last_texts + [text])[-self._cfg.flood_window:]

        moderation = moderate_text(text, repeats=repeats, flood=flood)
        if any(f in moderation.flags for f in (ModerationFlag.SPAM, ModerationFlag.AD)):
            user.warnings += 1
        self._repo.put_user(user)

        intent = classify_intent(text)
        priority = self._priority(user, intent, moderation)
        msg = Message(user_handle=user_handle, text=text, platform_ref=dict(platform_ref or {}),
                      intent=intent, priority=priority, moderation=moderation.to_dict())
        self._repo.put_message(msg)

        self._metrics["received"] += 1
        if ModerationFlag.SPAM in moderation.flags:
            self._metrics["spam"] += 1
            self._emit(ConversationEvents.SPAM_DETECTED, {"user": user_handle, "message_id": msg.id})
        if ModerationFlag.ABUSE in moderation.flags:
            self._metrics["abuse"] += 1
        if first_time:
            self._emit(ConversationEvents.USER_JOINED, {"user": user_handle})
        self._emit(ConversationEvents.MESSAGE_RECEIVED, {"id": msg.id, "intent": intent, "priority": priority})
        self._emit(ConversationEvents.INTENT_DETECTED, {"id": msg.id, "intent": intent})
        if moderation.severity == "high":
            self._metrics["escalated"] += 1
            self._emit(ConversationEvents.ESCALATED, {"id": msg.id, "flags": moderation.flags})
        return {"message": msg.to_dict(), "moderation": moderation.to_dict(),
                "moderation_suggestion": moderation.recommendation}

    def _priority(self, user: UserProfile, intent: str, moderation) -> str:
        if user.vip:
            return Priority.VIP
        if moderation.severity == "high":
            return Priority.LOW               # şüpheli mesaj kuyruğun altına
        if intent == "question":
            return Priority.HIGH
        return Priority.NORMAL

    # -- NİYET üretimi (yürütme YOK — Executive yürütür) ---------------- #
    def plan_reply(self, actor: str, message_id: str, reply_text: str, *,
                   private: bool = False) -> dict[str, Any]:
        """Bir mesaja cevap NİYETİ üretir (conversation.reply). GÖNDERMEZ — Executive yürütür."""
        self._authorize_writer(actor)
        msg = self._require_message(message_id)
        reply_text = self._require(reply_text, "cevap")
        capability = "conversation.private_reply" if private else "conversation.reply"
        ci = self._make_intent(capability,
                               {"in_reply_to": msg.id, "user_handle": msg.user_handle, "text": reply_text,
                                "platform_ref": msg.platform_ref}, label="Cevapla")
        self._metrics["replies_planned"] += 1
        self._emit(ConversationEvents.REPLY_REQUESTED, {"message_id": msg.id})
        return ci.to_dict()

    def moderation_intent(self, actor: str, message_id: str, action: str) -> dict[str, Any]:
        """Moderasyon NİYETİ üretir (delete/timeout/ban/pin). Yüksek-risk → requires_approval. YÜRÜTMEZ."""
        self._authorize_writer(actor)
        msg = self._require_message(message_id)
        cap = action if action.startswith("conversation.") else f"conversation.{action}"
        valid = {"conversation.delete", "conversation.timeout", "conversation.ban", "conversation.pin",
                 "conversation.reaction"}
        if cap not in valid:
            raise ValidationError(f"Geçersiz moderasyon aksiyonu: {action}")
        ci = self._make_intent(cap, {"message_id": msg.id, "user_handle": msg.user_handle,
                                     "platform_ref": msg.platform_ref}, label=f"Moderasyon: {action}")
        if ci.requires_approval:
            self._metrics["high_risk_intents"] += 1
            self._emit(ConversationEvents.APPROVAL_REQUIRED, {"message_id": msg.id, "capability": cap})
        return ci.to_dict()

    def mark_answered(self, actor: str, message_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        msg = self._require_message(message_id)
        msg.answered = True
        self._repo.put_message(msg)
        return msg.to_dict()

    # -- sıra / bağlam / özet ------------------------------------------- #
    def queue(self, actor: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Cevap bekleyen mesajlar — öncelik sırasıyla (VIP > high > normal > low), sonra zaman."""
        self._authorize(actor)
        msgs = self._repo.all_messages(unanswered_only=True)
        msgs.sort(key=lambda m: (-Priority.ORDER.get(m.priority, 1), m.ts))
        return [m.to_dict() for m in msgs[:int(limit)]]

    def summarize(self, actor: str) -> dict[str, Any]:
        """Deterministik konuşma özeti: mesaj/kullanıcı sayısı, niyet dağılımı, moderasyon, bekleyen soru."""
        self._authorize(actor)
        msgs = self._repo.all_messages()
        by_intent: dict[str, int] = {}
        flagged = 0
        for m in msgs:
            by_intent[m.intent] = by_intent.get(m.intent, 0) + 1
            if m.moderation.get("flags") and m.moderation["flags"] != [ModerationFlag.CLEAN]:
                flagged += 1
        pending = self._repo.message_count(unanswered_only=True)
        self._emit(ConversationEvents.SUMMARY_CREATED, {"messages": len(msgs)})
        return {"messages": len(msgs), "users": self._repo.user_count(), "by_intent": by_intent,
                "flagged": flagged, "pending": pending}

    def set_vip(self, actor: str, user_handle: str, vip: bool = True) -> dict[str, Any]:
        self._authorize_writer(actor)
        user = self._repo.get_user(user_handle)
        if user is None:
            user = UserProfile(handle=self._require(user_handle, "kullanıcı"))
        user.vip = bool(vip)
        self._repo.put_user(user)
        return user.to_dict()

    # -- sorgular -------------------------------------------------------- #
    def get_message(self, actor: str, message_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_message(message_id).to_dict()

    def list_messages(self, actor: str, *, unanswered_only: bool = False) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [m.to_dict() for m in self._repo.all_messages(unanswered_only=unanswered_only)]

    def get_user(self, actor: str, handle: str) -> dict[str, Any]:
        self._authorize(actor)
        u = self._repo.get_user(handle)
        if u is None:
            raise NotFoundError(f"Kullanıcı bulunamadı: {handle}")
        return u.to_dict()

    def list_users(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [u.to_dict() for u in self._repo.all_users()]

    def stats(self) -> dict[str, Any]:
        return {"users": self._repo.user_count(), "messages": self._repo.message_count(),
                "pending": self._repo.message_count(unanswered_only=True), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return conversation_contract()

    # ------------------------------------------------------------------ #
    def _make_intent(self, capability: str, request: dict, *, label: str = "") -> ConversationIntent:
        return ConversationIntent(capability=capability, request=dict(request or {}), label=label,
                                  requires_approval=capability in HIGH_RISK_CONV_INTENTS)

    def _require_message(self, message_id: str) -> Message:
        m = self._repo.get_message(message_id)
        if m is None:
            raise NotFoundError(f"Mesaj bulunamadı: {message_id}")
        return m

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' konuşma erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' konuşma yazma için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
