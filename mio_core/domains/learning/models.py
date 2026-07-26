"""MIO Core · Learning Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Öğrenme, innate çekirdeğin ÜZERİNE biner: sonuçları (beklenen↔gerçekleşen) gözler, tahmin-hatası hesaplar
ve bilişsel tabanı DETERMİNİSTİK günceller — inanç çürütme (E5), bilgi güven revizyonu ve tekrar eden
başarıdan HEURİSTİK EMERGENCE (Knowledge). LLM'den bağımsız."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LearningError(Exception):
    """Learning Domain temel hatası."""


class ValidationError(LearningError):
    pass


class UnauthorizedError(LearningError):
    pass


class NotFoundError(LearningError):
    pass


@dataclass
class LearningEvent:
    """Bir eylemin sonucundan öğrenme kaydı (deterministik geri-besleme birimi)."""
    action: str
    success: bool
    expected: str = ""
    actual: str = ""
    prediction_error: float = 0.0            # 0.0 (isabet) .. 1.0 (tam sapma)
    knowledge_id: Optional[str] = None       # güncellenen bilgi (varsa)
    belief_id: Optional[str] = None          # çürütülen inanç (varsa)
    tags: list[str] = field(default_factory=list)
    lesson: str = ""
    effects: list[str] = field(default_factory=list)   # uygulanan deterministik etkiler
    actor: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:16])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "action": self.action, "success": self.success, "expected": self.expected,
                "actual": self.actual, "prediction_error": self.prediction_error,
                "knowledge_id": self.knowledge_id, "belief_id": self.belief_id, "tags": list(self.tags),
                "lesson": self.lesson, "effects": list(self.effects), "actor": self.actor,
                "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LearningEvent":
        return cls(action=d["action"], success=bool(d["success"]), expected=d.get("expected", ""),
                   actual=d.get("actual", ""), prediction_error=float(d.get("prediction_error", 0.0)),
                   knowledge_id=d.get("knowledge_id"), belief_id=d.get("belief_id"),
                   tags=list(d.get("tags") or []), lesson=d.get("lesson", ""),
                   effects=list(d.get("effects") or []), actor=d.get("actor", ""),
                   id=d.get("id") or uuid4().hex[:16], created_at=d.get("created_at") or _now())


@dataclass
class LearningConfig:
    reinforce_step: float = 0.05             # başarıda bilgi güveni artışı
    penalize_step: float = 0.05              # başarısızlıkta bilgi güveni düşüşü
    emergence_min_successes: int = 3         # bir eylem-bağlamı bu kadar başarıyla → heuristik emergence
    history_limit: int = 100
    learner_actor: str = "Learning"          # Knowledge/E5'e karşı yazar kimliği
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Learning", "Reasoning", "Knowledge", "Memory"})
    writer_actors: set = field(default_factory=lambda: {"owner", "Executive", "Learning"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "LearningEvent", "LearningConfig",
    "LearningError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
