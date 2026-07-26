"""MIO Core · Memory Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

WM/STM/LTM/episodic/semantic/procedural bellek + deterministik yaşam-döngüsü (konsolidasyon/çürüme/buda).
Bounded context — kendi repository'si. authorization · validation · events · observability · error handling."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contract import CONTRACT_VERSION, MemEvents, memory_contract
from .models import (
    MemoryConfig,
    MemoryItem,
    MemoryType,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import MemoryRepository

logger = logging.getLogger("mio.domain.memory")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _keywords(text: str) -> list[str]:
    return [w.lower() for w in (text or "").split() if len(w) > 2]


class MemoryDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: MemoryRepository, *, bus=None,
                 config: Optional[MemoryConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or MemoryConfig()
        self._metrics = {"stored": 0, "recalled": 0, "consolidations": 0, "forgotten": 0, "evicted": 0}

    # ------------------------------------------------------------------ #
    def remember(self, actor: str, content: str, *, mtype: str = MemoryType.EPISODIC,
                 importance: float = 0.5, tags: Optional[list] = None, source: str = "") -> MemoryItem:
        self._authorize(actor)
        content = self._require_content(content)
        if mtype not in MemoryType.ALL:
            raise ValidationError(f"Geçersiz bellek tipi: {mtype}")
        importance = self._clamp(importance)
        if mtype == MemoryType.WORKING:
            self._enforce_wm_capacity()
        item = MemoryItem(content=content, mtype=mtype, importance=importance,
                          tags=list(tags or []), source=source or actor)
        self._repo.put(item)
        self._metrics["stored"] += 1
        self._emit(MemEvents.STORED, {"actor": actor, "id": item.id, "mtype": mtype})
        return item

    def note_working(self, actor: str, content: str, *, tags: Optional[list] = None) -> MemoryItem:
        return self.remember(actor, content, mtype=MemoryType.WORKING, importance=0.4, tags=tags)

    def recall(self, actor: str, query: str, *, mtype: Optional[str] = None,
               limit: int = 10) -> list[dict[str, Any]]:
        self._authorize(actor)
        items = self._repo.search(_keywords(query), mtype=mtype, limit=limit)
        for it in items:                                    # erişim = pekiştirme (deterministik)
            it.access_count += 1
            it.last_accessed = _now()
            it.strength = round(min(1.0, it.strength + 0.1), 4)
            self._repo.put(it)
        self._metrics["recalled"] += 1
        self._emit(MemEvents.RECALLED, {"actor": actor, "query": query, "hits": len(items)})
        return [it.to_dict() for it in items]

    def working_set(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [it.to_dict() for it in self._repo.list(MemoryType.WORKING)]

    def forget(self, actor: str, memory_id: str) -> None:
        self._authorize(actor)
        if not self._repo.delete(memory_id):
            raise NotFoundError(f"Bellek bulunamadı: {memory_id}")
        self._metrics["forgotten"] += 1
        self._emit(MemEvents.FORGOTTEN, {"actor": actor, "id": memory_id})

    # ------------------------------------------------------------------ #
    # Yaşam-döngüsü: konsolidasyon (STM→LTM, epizodik→semantik) + çürüme + buda
    # ------------------------------------------------------------------ #
    def consolidate(self, actor: str) -> dict[str, int]:
        self._authorize(actor)
        promoted = self._promote_stm_to_ltm()
        semantic = self._derive_semantic()
        pruned = self._decay_and_prune()
        result = {"promoted_to_ltm": promoted, "semantic_created": semantic, "pruned": pruned}
        self._metrics["consolidations"] += 1
        self._emit(MemEvents.CONSOLIDATED, result)
        logger.info("Memory: konsolidasyon %s (actor=%s)", result, actor)
        return result

    def _promote_stm_to_ltm(self) -> int:
        n = 0
        for it in self._repo.list(MemoryType.SHORT_TERM):
            if it.importance >= self._cfg.consolidation_importance:
                it.mtype, it.updated_at = MemoryType.LONG_TERM, _now()
                self._repo.put(it)
                n += 1
        return n

    def _derive_semantic(self) -> int:
        counts: dict[str, int] = {}
        for it in self._repo.list(MemoryType.EPISODIC):
            for t in it.tags:
                counts[t] = counts.get(t, 0) + 1
        existing = {t for it in self._repo.list(MemoryType.SEMANTIC) for t in it.tags}
        n = 0
        for tag, cnt in counts.items():
            if cnt >= self._cfg.semantic_min_occurrences and tag not in existing:
                self._repo.put(MemoryItem(content=f"«{tag}» hakkında örüntü ({cnt} deneyim)",
                                          mtype=MemoryType.SEMANTIC, importance=0.6, tags=[tag],
                                          source="consolidation"))
                n += 1
        return n

    def _decay_and_prune(self) -> int:
        pruned = 0
        for it in self._repo.list():
            if it.mtype in MemoryType.DURABLE or it.mtype == MemoryType.WORKING:
                continue
            it.strength = round(it.strength * (1 - self._cfg.decay_rate), 4)
            if it.strength < self._cfg.prune_below:
                self._repo.delete(it.id)
                pruned += 1
            else:
                self._repo.put(it)
        return pruned

    def _enforce_wm_capacity(self) -> None:
        wm = self._repo.list(MemoryType.WORKING)
        while len(wm) >= self._cfg.wm_capacity:
            victim = min(wm, key=lambda x: (x.strength, x.created_at))   # en zayıf/eski çıkar
            self._repo.delete(victim.id)
            wm = [w for w in wm if w.id != victim.id]
            self._metrics["evicted"] += 1
            self._emit(MemEvents.WORKING_EVICTED, {"id": victim.id})

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {t: self._repo.count(t) for t in sorted(MemoryType.ALL)} | {
            "total": self._repo.count(), **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return memory_contract()

    # ------------------------------------------------------------------ #
    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' bellek erişimi için yetkili değil")

    def _require_content(self, content: str) -> str:
        v = (content or "").strip()
        if not v:
            raise ValidationError("bellek içeriği boş olamaz")
        return v

    @staticmethod
    def _clamp(x: float) -> float:
        return max(0.0, min(1.0, float(x)))

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
