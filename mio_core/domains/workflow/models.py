"""MIO Core · Workflow Domain — modeller (production-grade), LLM-BAĞIMSIZ, DETERMİNİSTİK.

Görev grafı (DAG) + yürütme planı + checkpoint/resume + human-approval + rollback. **İş mantığı burada** (bağımlılık
çözümü, topolojik sıra, döngü tespiti, checkpoint durumu). Domain ConnectorManager çağırmaz; her görev bir
**CapabilityIntent** taşır — yürütmeye EXECUTIVE karar verir. Human-approval görevleri onaysız yürütülmez (Madde 24)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus:
    PENDING = "pending"              # bağımlılık bekliyor
    READY = "ready"                  # bağımlılık tamam, çalıştırılabilir
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED_APPROVAL = "blocked_approval"   # ready ama human-approval bekliyor (Madde 24)
    ALL = {PENDING, READY, RUNNING, COMPLETED, FAILED, SKIPPED, BLOCKED_APPROVAL}
    TERMINAL = {COMPLETED, FAILED, SKIPPED}


class WorkflowStatus:
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ALL = {DRAFT, RUNNING, PAUSED, COMPLETED, FAILED}


class WorkflowError(Exception):
    """Workflow Domain temel hatası."""


class ValidationError(WorkflowError):
    pass


class UnauthorizedError(WorkflowError):
    pass


class NotFoundError(WorkflowError):
    pass


class DAGError(WorkflowError):
    """Geçersiz görev grafı (döngü / eksik bağımlılık)."""


@dataclass
class WorkflowTask:
    name: str
    capability: str = ""             # görev bir CapabilityIntent taşır (yürütmeyi Executive yapar)
    request: dict = field(default_factory=dict)
    depends_on: list = field(default_factory=list)   # başka task adları
    requires_approval: bool = False
    status: str = TaskStatus.PENDING
    result: dict = field(default_factory=dict)
    error: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:8])

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "capability": self.capability, "request": dict(self.request),
                "depends_on": list(self.depends_on), "requires_approval": self.requires_approval,
                "status": self.status, "result": dict(self.result), "error": self.error}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WorkflowTask":
        return cls(name=d["name"], capability=d.get("capability", ""), request=dict(d.get("request") or {}),
                   depends_on=list(d.get("depends_on") or []),
                   requires_approval=bool(d.get("requires_approval", False)),
                   status=d.get("status", TaskStatus.PENDING), result=dict(d.get("result") or {}),
                   error=d.get("error", ""), id=d.get("id") or uuid4().hex[:8])


@dataclass
class Workflow:
    name: str
    tasks: list = field(default_factory=list)         # WorkflowTask
    status: str = WorkflowStatus.DRAFT
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def task_by_name(self, name: str) -> Optional[WorkflowTask]:
        return next((t for t in self.tasks if t.name == name), None)

    def task_by_id(self, tid: str) -> Optional[WorkflowTask]:
        return next((t for t in self.tasks if t.id == tid), None)

    def to_dict(self) -> dict[str, Any]:
        done = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        return {"id": self.id, "name": self.name, "status": self.status,
                "tasks": [t.to_dict() for t in self.tasks], "task_count": len(self.tasks),
                "completed": done, "progress": round(done / len(self.tasks), 3) if self.tasks else 0.0,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Workflow":
        return cls(name=d["name"], tasks=[WorkflowTask.from_dict(x) for x in d.get("tasks", [])],
                   status=d.get("status", WorkflowStatus.DRAFT), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now())


def validate_dag(tasks: list) -> None:
    """DAG doğrulama: eksik bağımlılık + döngü tespiti (deterministik). Hata → DAGError."""
    names = {t.name for t in tasks}
    if len(names) != len(tasks):
        raise DAGError("görev adları benzersiz olmalı")
    for t in tasks:
        for dep in t.depends_on:
            if dep not in names:
                raise DAGError(f"'{t.name}' eksik bağımlılık: '{dep}'")
    # döngü tespiti (DFS renklendirme)
    graph = {t.name: list(t.depends_on) for t in tasks}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in names}

    def _visit(n: str) -> None:
        color[n] = GRAY
        for m in graph[n]:
            if color[m] == GRAY:
                raise DAGError(f"döngü tespit edildi: '{n}' → '{m}'")
            if color[m] == WHITE:
                _visit(m)
        color[n] = BLACK

    for n in names:
        if color[n] == WHITE:
            _visit(n)


def topological_order(tasks: list) -> list:
    """Kahn algoritması — deterministik topolojik sıra (görev adları). Bağımsızlar ada göre sıralı (kararlı)."""
    names = [t.name for t in tasks]
    deps = {t.name: set(t.depends_on) for t in tasks}
    dependents: dict[str, list] = {n: [] for n in names}
    for t in tasks:
        for d in t.depends_on:
            dependents[d].append(t.name)
    ready = sorted([n for n in names if not deps[n]])
    order: list = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for m in sorted(dependents[n]):
            deps[m].discard(n)
            if not deps[m] and m not in order and m not in ready:
                ready.append(m)
        ready.sort()
    return order


@dataclass
class WorkflowConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Planning", "Scheduler"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Planning"})
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "TaskStatus", "WorkflowStatus", "WorkflowTask", "Workflow", "WorkflowConfig",
    "validate_dag", "topological_order",
    "WorkflowError", "ValidationError", "UnauthorizedError", "NotFoundError", "DAGError",
]
