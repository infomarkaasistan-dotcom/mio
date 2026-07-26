"""MIO Core · Communication Domain Service (production-grade), LLM-BAĞIMSIZ çekirdek.

Diyalog yönetimi + DETERMİNİSTİK niyet sınıflandırma + yanıt kompozisyonu. Yanıt üç kaynaktan gelir
(öncelik sırasıyla): (1) kayıtlı deterministik HANDLER (çekirdeğe yönlendirme), (2) opsiyonel LLM DANIŞMAN
(doğal ifade), (3) dürüst FALLBACK. LLM erişilemezse domain çalışmaya devam eder. Communication KARAR VERMEZ.
authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, CommEvents, communication_contract
from .models import (
    CommunicationConfig,
    Conversation,
    INTENT_KEYWORDS,
    Intent,
    NotFoundError,
    ResponseSource,
    Turn,
    UnauthorizedError,
    ValidationError,
)
from .repository import ConversationRepository

logger = logging.getLogger("mio.domain.communication")

Handler = Callable[[str, dict], str]        # (text, ctx) -> reply
Advisor = Callable[[str], Optional[str]]    # (prompt) -> reply | None


class CommunicationDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: ConversationRepository, *, advisor: Optional[Advisor] = None,
                 bus=None, config: Optional[CommunicationConfig] = None) -> None:
        self._repo = repository
        self._advisor = advisor            # opsiyonel LLM danışman (callable)
        self._bus = bus
        self._cfg = config or CommunicationConfig()
        self._handlers: dict[str, Handler] = {}
        self._metrics = {"turns": 0, "replies": 0, "handler": 0, "advisor": 0, "fallback": 0}

    # ------------------------------------------------------------------ #
    def register_handler(self, intent: str, handler: Handler) -> None:
        """Bir niyet için deterministik çekirdek handler'ı bağlar (kompozisyon-zamanı DI)."""
        if intent not in Intent.ALL:
            raise ValidationError(f"Geçersiz niyet: {intent}")
        self._handlers[intent] = handler

    def classify(self, text: str) -> str:
        """DETERMİNİSTİK niyet sınıflandırma (kural tabanlı, LLM'siz). Aynı girdi → aynı niyet."""
        t = (text or "").lower()
        for intent, keywords in INTENT_KEYWORDS:
            if any(k in t for k in keywords):
                return intent
        return Intent.UNKNOWN

    def converse(self, actor: str, text: str, *, conversation_id: Optional[str] = None) -> dict[str, Any]:
        """Bir kullanıcı turunu işler: niyet sınıflandır → yanıtla (handler→advisor→fallback) → kaydet."""
        self._authorize(actor)
        text = self._require(text, "mesaj")
        conv = self._load_or_create(conversation_id)
        intent = self.classify(text)
        conv.add(Turn(role="user", text=text, intent=intent))
        self._metrics["turns"] += 1
        self._emit(CommEvents.TURN_RECEIVED, {"actor": actor, "conversation_id": conv.id, "intent": intent})
        self._emit(CommEvents.INTENT_CLASSIFIED, {"conversation_id": conv.id, "intent": intent})

        reply, source = self._respond(intent, text, {"actor": actor, "conversation_id": conv.id,
                                                      "intent": intent})
        conv.add(Turn(role="assistant", text=reply, intent=intent, source=source))
        self._enforce_turn_cap(conv)
        self._repo.put(conv)
        self._metrics["replies"] += 1
        self._metrics[source] = self._metrics.get(source, 0) + 1
        self._emit(CommEvents.REPLIED, {"conversation_id": conv.id, "intent": intent, "source": source})
        return {"conversation_id": conv.id, "intent": intent, "reply": reply, "source": source}

    def history(self, actor: str, conversation_id: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        conv = self._repo.get(conversation_id)
        if conv is None:
            raise NotFoundError(f"Konuşma bulunamadı: {conversation_id}")
        return [t.to_dict() for t in conv.turns]

    def conversations(self, actor: str, *, limit: int = 50) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [{"id": c.id, "turns": len(c.turns), "updated_at": c.updated_at}
                for c in self._repo.recent(limit)]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"conversations": self._repo.count(), **self._metrics,
                "handlers_registered": sorted(self._handlers), "advisor": self._advisor is not None,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return communication_contract()

    # ------------------------------------------------------------------ #
    def _respond(self, intent: str, text: str, ctx: dict) -> tuple[str, str]:
        # 1) deterministik handler
        handler = self._handlers.get(intent)
        if handler is not None:
            try:
                reply = (handler(text, ctx) or "").strip()
                if reply:
                    return reply, ResponseSource.HANDLER
            except Exception as exc:  # noqa: BLE001 — handler hatası yanıtı düşürmez, dürüstçe devam
                logger.warning("Communication handler hatası (%s): %s", intent, exc)
        # 2) opsiyonel LLM danışman
        if self._advisor is not None:
            try:
                reply = (self._advisor(text) or "").strip()
                if reply:
                    return reply, ResponseSource.ADVISOR
            except Exception as exc:  # noqa: BLE001 — LLM erişilemez → dürüst geri-dönüş
                logger.warning("Communication advisor hatası: %s", exc)
        # 3) dürüst geri-dönüş (uydurma yok)
        return (self._fallback(intent), ResponseSource.FALLBACK)

    @staticmethod
    def _fallback(intent: str) -> str:
        if intent == Intent.GREETING:
            return "Merhaba. Ben MIO. Uzun-vadeli hedeflerini yönetmek için buradayım."
        return ("Bunu şu an güvenle yanıtlayamıyorum (bu niyet için bağlı bir yetenek/danışman yok). "
                "Ne yapmak istediğini biraz daha açar mısın?")

    def _load_or_create(self, conversation_id: Optional[str]) -> Conversation:
        if conversation_id:
            conv = self._repo.get(conversation_id)
            if conv is None:
                raise NotFoundError(f"Konuşma bulunamadı: {conversation_id}")
            return conv
        return Conversation()

    def _enforce_turn_cap(self, conv: Conversation) -> None:
        if len(conv.turns) > self._cfg.max_turns:
            conv.turns = conv.turns[-self._cfg.max_turns:]   # en eski turları buda (sınırlı bellek)

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' konuşma için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
