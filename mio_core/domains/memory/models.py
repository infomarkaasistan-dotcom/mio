"""MIO Core · Memory Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Bellek katmanları: Working (WM) · Short-Term (STM) · Long-Term (LTM) · Episodic · Semantic · Procedural.
Bounded context — çekirdeğe eklenmez, kendi repository'si vardır. Deterministik yaşam-döngüsü (konsolidasyon,
çürüme, buda)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryType:
    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    ALL = {WORKING, SHORT_TERM, LONG_TERM, EPISODIC, SEMANTIC, PROCEDURAL}
    # Buda/çürümeden korunanlar (kalıcı katmanlar)
    DURABLE = {LONG_TERM, SEMANTIC, PROCEDURAL}


class MemoryError(Exception):
    """Memory Domain temel hatası."""


class ValidationError(MemoryError):
    pass


class UnauthorizedError(MemoryError):
    pass


class NotFoundError(MemoryError):
    pass


@dataclass
class MemoryItem:
    content: str
    mtype: str = MemoryType.EPISODIC
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    source: str = ""
    strength: float = 1.0
    access_count: int = 0
    id: str = field(default_factory=lambda: uuid4().hex[:16])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    last_accessed: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "content": self.content, "mtype": self.mtype, "importance": self.importance,
                "tags": list(self.tags), "source": self.source, "strength": self.strength,
                "access_count": self.access_count, "created_at": self.created_at,
                "updated_at": self.updated_at, "last_accessed": self.last_accessed}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MemoryItem":
        return cls(content=d["content"], mtype=d.get("mtype", MemoryType.EPISODIC),
                   importance=float(d.get("importance", 0.5)), tags=list(d.get("tags") or []),
                   source=d.get("source", ""), strength=float(d.get("strength", 1.0)),
                   access_count=int(d.get("access_count", 0)), id=d.get("id") or uuid4().hex[:16],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now(),
                   last_accessed=d.get("last_accessed"))


@dataclass
class MemoryConfig:
    wm_capacity: int = 7                          # 7±2 çalışma belleği sınırı
    consolidation_importance: float = 0.6         # STM→LTM eşiği
    semantic_min_occurrences: int = 2             # bir etiket bu kadar epizotta → semantik örüntü
    decay_rate: float = 0.1                       # her konsolidasyonda çürüme
    prune_below: float = 0.15                     # bu gücün altı budanır (durable hariç)
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Knowledge", "Learning", "Memory", "Communication"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors
