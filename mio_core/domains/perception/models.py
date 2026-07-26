"""MIO Core · Perception Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Algı, diyalog-DIŞI dış sinyalleri (olay/ölçüm/gözlem/uyarı) DETERMİNİSTİK tipli PERCEPT'lere normalize eder
ve bilişe yönlendirir: gözlemler E5'e (inanç oluşumu), deneyimler Memory'ye (epizodik), yüksek belirginlik
Attention'a (tetik). Kanıt uydurulmaz; yalnız gelen sinyal kaydedilir ve türetilir."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PerceptKind:
    OBSERVATION = "observation"   # dünya hakkında bir olgu (inanç oluşumuna gider)
    EVENT = "event"               # bir şey oldu
    METRIC = "metric"             # ölçüm/veri
    SIGNAL = "signal"             # genel sinyal
    ALERT = "alert"               # dikkat gerektirir
    ALL = {OBSERVATION, EVENT, METRIC, SIGNAL, ALERT}


# Türüne göre deterministik varsayılan belirginlik (salience)
DEFAULT_SALIENCE = {
    PerceptKind.ALERT: 0.9, PerceptKind.EVENT: 0.6, PerceptKind.OBSERVATION: 0.5,
    PerceptKind.METRIC: 0.4, PerceptKind.SIGNAL: 0.3,
}


class PerceptionError(Exception):
    """Perception Domain temel hatası."""


class ValidationError(PerceptionError):
    pass


class UnauthorizedError(PerceptionError):
    pass


class NotFoundError(PerceptionError):
    pass


@dataclass
class Percept:
    source: str
    kind: str
    content: str
    subject: str = ""
    valence: float = 0.0
    salience: float = 0.5
    tags: list[str] = field(default_factory=list)
    routed: list[str] = field(default_factory=list)   # yönlendirildiği bilişsel sink'ler
    actor: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:16])
    at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "source": self.source, "kind": self.kind, "content": self.content,
                "subject": self.subject, "valence": self.valence, "salience": self.salience,
                "tags": list(self.tags), "routed": list(self.routed), "actor": self.actor, "at": self.at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Percept":
        return cls(source=d["source"], kind=d["kind"], content=d["content"], subject=d.get("subject", ""),
                   valence=float(d.get("valence", 0.0)), salience=float(d.get("salience", 0.5)),
                   tags=list(d.get("tags") or []), routed=list(d.get("routed") or []),
                   actor=d.get("actor", ""), id=d.get("id") or uuid4().hex[:16], at=d.get("at") or _now())


@dataclass
class PerceptionConfig:
    attention_threshold: float = 0.7     # bu belirginliğin üstü dikkat tetikler
    route_to_cognitive: bool = True      # OBSERVATION + subject → E5 belief
    route_to_memory: bool = True         # tüm percept'ler → epizodik bellek (best-effort)
    memory_actor: str = "Memory"         # bellek yönlendirmesinde yetkili sink kimliği (MemoryConfig'te yetkili)
    history_limit: int = 200
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Perception", "Communication", "Operations"})
    writer_actors: set = field(default_factory=lambda: {"owner", "Executive", "Perception", "Operations"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "PerceptKind", "DEFAULT_SALIENCE", "Percept", "PerceptionConfig",
    "PerceptionError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
