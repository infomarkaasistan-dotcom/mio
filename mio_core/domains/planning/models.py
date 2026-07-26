"""MIO Core · Planning Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Bir PLAN, bir amaca (goal) hizmet eden; bağımlılık-sıralı, yetenek-farkında, DETERMİNİSTİK adım dizisidir.
Planning KARAR VERMEZ ve YÜRÜTMEZ — plan üretir, sıralar, fizibilitesini denetler. Yürütme (Execution) ve
onay (E4 Governance / Executive) ayrı katmanlardır. 'Execution asla tek başına karar vermez'."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sid() -> str:
    return uuid4().hex[:12]


class PlanStatus:
    DRAFT = "draft"                # düzenleniyor (sıralama geçersiz)
    SEQUENCED = "sequenced"        # bağımlılıklar çözüldü, sıralı
    APPROVED = "approved"          # gözden geçirildi (Executive/E4) — yürütmeye hazır
    ABANDONED = "abandoned"
    ALL = {DRAFT, SEQUENCED, APPROVED, ABANDONED}


class PlanError(Exception):
    """Planning Domain temel hatası."""


class ValidationError(PlanError):
    pass


class UnauthorizedError(PlanError):
    pass


class NotFoundError(PlanError):
    pass


class InfeasiblePlanError(PlanError):
    """Plan fizibil değil (döngü / çözülemeyen bağımlılık)."""


@dataclass
class PlanStep:
    description: str
    requires: list[str] = field(default_factory=list)   # önce tamamlanması gereken adım id'leri
    capability: Optional[str] = None                     # gereken yetenek adı (varsa)
    expected: str = ""                                   # beklenen sonuç (ölçülebilir niyet)
    status: str = "pending"                              # pending → ordered → done
    order: int = -1                                      # sıralanınca atanır (deterministik)
    id: str = field(default_factory=_sid)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "description": self.description, "requires": list(self.requires),
                "capability": self.capability, "expected": self.expected, "status": self.status,
                "order": self.order}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PlanStep":
        return cls(description=d["description"], requires=list(d.get("requires") or []),
                   capability=d.get("capability"), expected=d.get("expected", ""),
                   status=d.get("status", "pending"), order=int(d.get("order", -1)),
                   id=d.get("id") or _sid())


@dataclass
class Plan:
    objective: str
    goal_id: Optional[str] = None
    status: str = PlanStatus.DRAFT
    steps: list[PlanStep] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex[:16])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "objective": self.objective, "goal_id": self.goal_id,
                "status": self.status, "steps": [s.to_dict() for s in self.steps],
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Plan":
        return cls(objective=d["objective"], goal_id=d.get("goal_id"),
                   status=d.get("status", PlanStatus.DRAFT),
                   steps=[PlanStep.from_dict(s) for s in d.get("steps") or []],
                   id=d.get("id") or uuid4().hex[:16],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now())

    def step(self, step_id: str) -> Optional[PlanStep]:
        return next((s for s in self.steps if s.id == step_id), None)


@dataclass
class PlanConfig:
    max_steps: int = 200
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Planning", "Reasoning", "Knowledge", "Learning"})
    writer_actors: set = field(default_factory=lambda: {"owner", "Executive", "Planning"})
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "Plan", "PlanStep", "PlanStatus", "PlanConfig",
    "PlanError", "ValidationError", "UnauthorizedError", "NotFoundError", "InfeasiblePlanError",
]
