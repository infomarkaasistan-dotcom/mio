"""MIO Core · Execution Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Execution, onaylı bir kararı/planı GERÇEK araçlarla (Tool Orchestrator) hayata geçirir. Anayasa gereği
**Execution asla tek başına karar VERMEZ**: her yürütme bir yetkilendirmeye bağlıdır (onaylı plan ya da
karar referansı). Bir workflow, onaylı bir planın sıralı adımlarını çalıştırır (fail-fast) ve her adımı
denetime yazar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunKind:
    STEP = "step"                 # tek yetenek çağrısı
    PLAN = "plan"                 # onaylı planın workflow yürütmesi
    ALL = {STEP, PLAN}


class RunStatus:
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"           # governance/authz ile engellendi
    ALL = {COMPLETED, FAILED, BLOCKED}


class ExecutionError(Exception):
    """Execution Domain temel hatası."""


class ValidationError(ExecutionError):
    pass


class UnauthorizedError(ExecutionError):
    pass


class NotFoundError(ExecutionError):
    pass


class UnauthorizedExecutionError(ExecutionError):
    """Yetkilendirme (onaylı plan/karar) olmadan yürütme girişimi — Execution tek başına karar vermez."""


@dataclass
class ExecutionRun:
    kind: str
    actor: str = ""
    authorization: str = ""              # onaylı plan/karar referansı (zorunlu)
    plan_id: Optional[str] = None
    status: str = RunStatus.COMPLETED
    steps: list[dict[str, Any]] = field(default_factory=list)   # adım-adım sonuçlar (denetim)
    started_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None
    id: str = field(default_factory=lambda: uuid4().hex[:16])

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "actor": self.actor,
                "authorization": self.authorization, "plan_id": self.plan_id, "status": self.status,
                "steps": self.steps, "started_at": self.started_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExecutionRun":
        return cls(kind=d["kind"], actor=d.get("actor", ""), authorization=d.get("authorization", ""),
                   plan_id=d.get("plan_id"), status=d.get("status", RunStatus.COMPLETED),
                   steps=list(d.get("steps") or []), started_at=d.get("started_at") or _now(),
                   finished_at=d.get("finished_at"), id=d.get("id") or uuid4().hex[:16])


@dataclass
class ExecutionConfig:
    require_authorization: bool = True   # Anayasa: yürütme yetkilendirme ister (Execution tek başına karar vermez)
    default_action: str = "run"          # plan adımı için varsayılan aksiyon
    history_limit: int = 100
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Workflow", "Engineering"})
    writer_actors: set = field(default_factory=lambda: {"owner", "Executive", "Operations", "Workflow"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "RunKind", "RunStatus", "ExecutionRun", "ExecutionConfig",
    "ExecutionError", "ValidationError", "UnauthorizedError", "NotFoundError",
    "UnauthorizedExecutionError",
]
