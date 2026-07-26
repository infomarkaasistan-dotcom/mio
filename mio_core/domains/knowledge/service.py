"""MIO Core · Knowledge Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Innate `KnowledgeBase`'i governance kabuğuyla SARAR (çekirdeğe dokunmadan): yaşayan bilgi öğrenme
(write-through kalıcı), retrieve, bağlama deterministik UYGULAMA (LLM'siz karar üretimi), güven revizyonu,
unutma. authorization · validation · events · observability · error handling. Innate bilgi doktrinerdir."""

from __future__ import annotations

import logging
from typing import Any, Optional, Union

from mio_core.knowledge import KnowledgeBase, KnowledgeItem, KnowledgeType

from .contract import CONTRACT_VERSION, KnowEvents, knowledge_contract
from .models import (
    ImmutableKnowledgeError,
    KnowledgeConfig,
    LearnCommand,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    is_innate,
    learned_source,
)
from .repository import KnowledgeRepository

logger = logging.getLogger("mio.domain.knowledge")


class KnowledgeDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, base: KnowledgeBase, repository: KnowledgeRepository, *, bus=None,
                 config: Optional[KnowledgeConfig] = None) -> None:
        self._base = base
        self._repo = repository
        self._bus = bus
        self._cfg = config or KnowledgeConfig()
        self._metrics = {"learned": 0, "retrieved": 0, "applied": 0, "reinforced": 0, "forgotten": 0}

    # ------------------------------------------------------------------ #
    def learn(self, actor: str, command: Union[LearnCommand, dict, None] = None, **kw) -> KnowledgeItem:
        """Yaşayan (learned) bilgi öğren — çekirdeğe ekler + kalıcılaştırır (write-through)."""
        self._authorize_writer(actor)
        cmd = self._as_command(command, kw)
        ktype = self._parse_ktype(cmd.ktype)
        name = self._require(cmd.name, "bilgi adı")
        statement = self._require(cmd.statement, "bilgi ifadesi")
        if not self._cfg.valid_domain(cmd.domain):
            raise ValidationError(f"Geçersiz bilgi alanı: {cmd.domain}")
        confidence = self._clamp(cmd.confidence)
        when, then, steps = list(cmd.when or []), (cmd.then or "").strip(), list(cmd.steps or [])
        if ktype in self._cfg.applicable_types and not (when and then):
            raise ValidationError(
                f"Uygulanabilir bilgi ({ktype.value}) 'when' koşulları ve 'then' sonucu gerektirir")
        item = KnowledgeItem(ktype=ktype, name=name, statement=statement, domain=cmd.domain,
                             when=when, then=then, steps=steps, confidence=confidence,
                             tags=list(cmd.tags or []), source=learned_source(actor))
        self._base.add(item)
        self._repo.put(item)                                        # write-through kalıcılık
        self._metrics["learned"] += 1
        self._emit(KnowEvents.LEARNED, {"actor": actor, "id": item.id, "ktype": ktype.value, "name": name})
        return item

    def what_do_i_know(self, actor: str, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """'X hakkında ne biliyorum?' — deterministik geri getirme (uydurma yok)."""
        self._authorize(actor)
        items = self._base.retrieve(query, limit=limit)
        self._metrics["retrieved"] += 1
        self._emit(KnowEvents.RETRIEVED, {"actor": actor, "query": query, "hits": len(items)})
        return [it.to_dict() for it in items]

    def apply(self, actor: str, context_tags) -> list[dict[str, Any]]:
        """Bağlama UYGULANABİLİR bilgiyi değerlendirir → deterministik öneriler (LLM'e gerek yok)."""
        self._authorize(actor)
        tags = set(context_tags or [])
        results = self._base.apply(tags)
        self._metrics["applied"] += 1
        self._emit(KnowEvents.APPLIED, {"actor": actor, "context": sorted(tags), "matches": len(results)})
        return [{"item_id": a.item_id, "name": a.name, "recommendation": a.recommendation,
                 "confidence": a.confidence, "ktype": a.ktype} for a in results]

    def list_knowledge(self, actor: str, *, ktype: Optional[str] = None,
                       domain: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        kt = self._parse_ktype(ktype) if ktype else None
        return [it.to_dict() for it in self._base.list(ktype=kt, domain=domain)]

    def reinforce(self, actor: str, item_id: str, *, delta: Optional[float] = None) -> float:
        """Güven revizyonu (belief revision) — yaşayan bilgi için. Innate doktriner, değiştirilemez."""
        self._authorize_writer(actor)
        item = self._living_or_raise(item_id)
        step = self._cfg.reinforce_step if delta is None else float(delta)
        item.confidence = self._clamp(item.confidence + step)
        self._base.add(item)                                        # aynı id → günceller
        self._repo.put(item)
        self._metrics["reinforced"] += 1
        self._emit(KnowEvents.REINFORCED, {"actor": actor, "id": item_id, "confidence": item.confidence})
        return item.confidence

    def forget(self, actor: str, item_id: str) -> None:
        """Yaşayan bilgiyi unut. Innate bilgi silinemez (doktriner)."""
        self._authorize_writer(actor)
        self._living_or_raise(item_id)
        self._base.remove(item_id)
        self._repo.delete(item_id)
        self._metrics["forgotten"] += 1
        self._emit(KnowEvents.FORGOTTEN, {"actor": actor, "id": item_id})

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        items = self._base.list()
        by_type = {t.value: 0 for t in KnowledgeType}
        innate = learned = applicable = 0
        for it in items:
            by_type[it.ktype.value] += 1
            if is_innate(it):
                innate += 1
            else:
                learned += 1
            if it.ktype in self._cfg.applicable_types and it.when:
                applicable += 1
        return {"total": len(items), "innate": innate, "learned": learned, "applicable": applicable,
                "durable_learned": self._repo.count(), "by_type": by_type,
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return knowledge_contract()

    # ------------------------------------------------------------------ #
    def _living_or_raise(self, item_id: str) -> KnowledgeItem:
        item = self._base.get(item_id)
        if item is None:
            raise NotFoundError(f"Bilgi bulunamadı: {item_id}")
        if is_innate(item):
            raise ImmutableKnowledgeError(f"Innate (doktriner) bilgi değiştirilemez/silinemez: {item_id}")
        return item

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' bilgi erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' bilgi yazma (learn/reinforce/forget) için yetkili değil")

    @staticmethod
    def _as_command(command, kw: dict) -> LearnCommand:
        if isinstance(command, LearnCommand):
            return command
        if isinstance(command, dict):
            return LearnCommand(**command)
        if command is None:
            return LearnCommand(**kw)
        raise ValidationError("learn: LearnCommand, dict veya adlandırılmış argüman bekler")

    @staticmethod
    def _parse_ktype(value) -> KnowledgeType:
        if isinstance(value, KnowledgeType):
            return value
        try:
            return KnowledgeType(str(value))
        except ValueError as exc:
            raise ValidationError(f"Geçersiz bilgi tipi: {value}") from exc

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    @staticmethod
    def _clamp(x: float) -> float:
        return round(max(0.0, min(1.0, float(x))), 4)

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
