"""MIO Core · Conversation Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ConversationEvents:
    MESSAGE_RECEIVED = "conversation.message_received"
    INTENT_DETECTED = "conversation.intent_detected"
    PRIORITY_CHANGED = "conversation.priority_changed"
    REPLY_REQUESTED = "conversation.reply_requested"
    SPAM_DETECTED = "conversation.spam_detected"
    USER_JOINED = "conversation.user_joined"
    TOPIC_CHANGED = "conversation.topic_changed"
    SUMMARY_CREATED = "conversation.summary_created"
    ESCALATED = "conversation.escalated"
    APPROVAL_REQUIRED = "conversation.approval_required"


OPERATIONS = ("receive", "plan_reply", "moderation_intent", "queue", "summarize", "set_vip",
              "get_message", "list_messages", "get_user", "list_users", "stats")


def conversation_contract() -> dict[str, Any]:
    return {
        "domain": "conversation",
        "version": CONTRACT_VERSION,
        "description": "Gerçek zamanlı etkileşim mantığı: mesaj alma/sınıflandırma/niyet + bağlam + spam/flood/"
                       "hakaret TESPİTİ + öncelik (VIP) + moderasyon ÖNERİSİ + sıra + özet. Platformları BİLMEZ; "
                       "yalnız CapabilityIntent (conversation.reply/delete/ban...) üretir. Moderasyon KARAR VERMEZ "
                       "(Executive'e öneri). Yüksek-risk niyet onay ister (Madde 24).",
        "operations": list(OPERATIONS),
        "events": [ConversationEvents.MESSAGE_RECEIVED, ConversationEvents.INTENT_DETECTED,
                   ConversationEvents.PRIORITY_CHANGED, ConversationEvents.REPLY_REQUESTED,
                   ConversationEvents.SPAM_DETECTED, ConversationEvents.USER_JOINED,
                   ConversationEvents.TOPIC_CHANGED, ConversationEvents.SUMMARY_CREATED,
                   ConversationEvents.ESCALATED, ConversationEvents.APPROVAL_REQUIRED],
        "intents": ["question", "statement", "command", "greeting", "feedback"],
        "moderation_flags": ["spam", "flood", "abuse", "ad", "clean"],
        "priorities": ["low", "normal", "high", "vip"],
        "capability_targets": ["conversation.receive", "conversation.reply", "conversation.private_reply",
                               "conversation.broadcast", "conversation.pin", "conversation.delete",
                               "conversation.timeout", "conversation.ban", "conversation.reaction",
                               "notification.send"],
        "invariants": ["platformları (YouTube/Discord/Slack/...) İSİM olarak bile bilmez",
                       "ConnectorManager/connector ÇAĞIRMAZ; doğrudan cevap GÖNDEREMEZ; yalnız niyet üretir",
                       "moderasyon TESPİT eder, KARAR VERMEZ — Executive'e öneri (sil/engelle/cevapla/yoksay)",
                       "sınıflandırma/öncelik/moderasyon DETERMİNİSTİK; LLM yalnız içerik (danışman)",
                       "yüksek-risk niyet (delete/timeout/ban/broadcast/pin) onay ister (Madde 24)",
                       "öğrenme yapmaz (Learning'e sinyal gönderilebilir)"],
    }
