"""MIO Core · Business & Operations Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Deterministik iş/operasyon: süreç (adım/rol/süre/otomatikleştirilebilirlik) registry + darboğaz analizi +
iş kuralı motoru (koşul→aksiyon). Uydurma yok; öneriler yalnız girilen süreç/kurallardan türetilir."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProcessStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"
    ALL = {DRAFT, ACTIVE, RETIRED}


class BusinessError(Exception):
    """Business & Operations Domain temel hatası."""


class ValidationError(BusinessError):
    pass


class UnauthorizedError(BusinessError):
    pass


class NotFoundError(BusinessError):
    pass


@dataclass
class ProcessStep:
    name: str
    role: str = ""
    duration_hours: float = 1.0
    automatable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "role": self.role, "duration_hours": self.duration_hours,
                "automatable": self.automatable}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProcessStep":
        return cls(name=d["name"], role=d.get("role", ""),
                   duration_hours=float(d.get("duration_hours", 1.0)),
                   automatable=bool(d.get("automatable", False)))


@dataclass
class Process:
    name: str
    steps: list[ProcessStep] = field(default_factory=list)
    status: str = ProcessStatus.ACTIVE
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "status": self.status,
                "steps": [s.to_dict() for s in self.steps], "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Process":
        return cls(name=d["name"], steps=[ProcessStep.from_dict(s) for s in d.get("steps") or []],
                   status=d.get("status", ProcessStatus.ACTIVE), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class BusinessRule:
    name: str
    when: list[str] = field(default_factory=list)   # tüm etiketler bağlamda → tetiklenir
    then: str = ""                                   # önerilen aksiyon
    priority: int = 50
    id: str = field(default_factory=lambda: uuid4().hex[:12])

    def matches(self, tags: set[str]) -> bool:
        return bool(self.when) and all(w in tags for w in self.when)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "when": list(self.when), "then": self.then,
                "priority": self.priority}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BusinessRule":
        return cls(name=d["name"], when=list(d.get("when") or []), then=d.get("then", ""),
                   priority=int(d.get("priority", 50)), id=d.get("id") or uuid4().hex[:12])


@dataclass
class BizConfig:
    bottleneck_ratio: float = 0.4      # tek adım toplam sürenin bu oranını aşarsa darboğaz
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Business", "Workflow", "Planning", "Finance", "Reasoning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Business", "Workflow"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "ProcessStatus", "ProcessStep", "Process", "BusinessRule", "BizConfig",
    "BusinessError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
