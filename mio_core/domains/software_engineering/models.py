"""MIO Core · Software Engineering Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Deterministik SE çekirdeği: stdlib `ast` ile GERÇEK Python kod analizi + placeholder/TODO/stub tespiti
(Anayasa 'placeholder yok' kuralını yeteneğe çevirir) + artifact/engineering-task registry. Kod-üretimi
LLM danışmana kalır (karar vermez); doğrulama deterministiktir."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskKind:
    FEATURE = "feature"
    BUG = "bug"
    REFACTOR = "refactor"
    TEST = "test"
    DOCS = "docs"
    ALL = {FEATURE, BUG, REFACTOR, TEST, DOCS}


class TaskStatus:
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    ALL = {OPEN, IN_PROGRESS, DONE, BLOCKED}


class SEError(Exception):
    """Software Engineering Domain temel hatası."""


class ValidationError(SEError):
    pass


class UnauthorizedError(SEError):
    pass


class NotFoundError(SEError):
    pass


@dataclass
class Artifact:
    """İzlenen bir kod artefaktı (modül/dosya/bileşen)."""
    path: str
    kind: str = "module"
    language: str = "python"
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "path": self.path, "kind": self.kind, "language": self.language,
                "description": self.description, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Artifact":
        return cls(path=d["path"], kind=d.get("kind", "module"), language=d.get("language", "python"),
                   description=d.get("description", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class EngTask:
    """Yazılım mühendisliği görevi (feature/bug/refactor/test/docs)."""
    title: str
    kind: str = TaskKind.FEATURE
    status: str = TaskStatus.OPEN
    detail: str = ""
    artifact_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "kind": self.kind, "status": self.status,
                "detail": self.detail, "artifact_id": self.artifact_id,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EngTask":
        return cls(title=d["title"], kind=d.get("kind", TaskKind.FEATURE),
                   status=d.get("status", TaskStatus.OPEN), detail=d.get("detail", ""),
                   artifact_id=d.get("artifact_id", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now())


@dataclass
class SEConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Engineering", "Operations", "Planning", "Workflow", "Reasoning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Engineering", "Operations", "Workflow"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "TaskKind", "TaskStatus", "Artifact", "EngTask", "SEConfig",
    "SEError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
