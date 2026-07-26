"""MIO Core · Reasoning Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Muhakeme bir SÜREÇTİR: bilgi (Knowledge.apply) + inançlar (E5 Cognitive) + muhakeme şablonları
birleştirilerek DETERMİNİSTİK çıkarım üretilir. Her muhakeme oturumu açıklanabilirlik/denetim için
iz (trace) olarak kalıcılaştırılır. LLM'den bağımsızdır."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReasoningKind:
    DEDUCE = "deduce"                 # ileri-zincirleme: bağlama uygulanabilir bilgi → sonuç
    DELIBERATE = "deliberate"         # şablonlu değerlendirme (adım adım muhakeme)
    CONSISTENCY = "consistency"       # inanç çelişkisi denetimi
    ALL = {DEDUCE, DELIBERATE, CONSISTENCY}


class ReasoningError(Exception):
    """Reasoning Domain temel hatası."""


class ValidationError(ReasoningError):
    pass


class UnauthorizedError(ReasoningError):
    pass


class NotFoundError(ReasoningError):
    pass


@dataclass
class ReasoningTrace:
    """Denetlenebilir, deterministik muhakeme izi (açıklanabilirlik)."""
    kind: str
    inputs: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 0.0
    actor: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:16])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "inputs": self.inputs, "steps": self.steps,
                "conclusion": self.conclusion, "confidence": self.confidence, "actor": self.actor,
                "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReasoningTrace":
        return cls(kind=d["kind"], inputs=dict(d.get("inputs") or {}), steps=list(d.get("steps") or []),
                   conclusion=d.get("conclusion", ""), confidence=float(d.get("confidence", 0.0)),
                   actor=d.get("actor", ""), id=d.get("id") or uuid4().hex[:16],
                   created_at=d.get("created_at") or _now())


@dataclass
class ReasoningConfig:
    default_template: str = "karar-muhakemesi"           # innate ReasoningTemplate adı
    reasoning_actor: str = "Reasoning"                   # Knowledge Domain'e karşı okuyucu kimliği
    history_limit: int = 50
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Reasoning", "Planning", "Knowledge", "Learning"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors


__all__ = [
    "ReasoningKind", "ReasoningTrace", "ReasoningConfig",
    "ReasoningError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
