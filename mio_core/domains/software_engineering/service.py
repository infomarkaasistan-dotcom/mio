"""MIO Core · Software Engineering Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Deterministik statik analiz (ast) + Anayasa 'placeholder yok' quality gate + artifact/engineering-task
registry. Kod-üretimi LLM danışmana bırakılır (karar vermez); DOĞRULAMA burada deterministiktir.
authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .analyzer import analyze
from .contract import CONTRACT_VERSION, SEEvents, software_contract
from .models import (
    Artifact,
    EngTask,
    NotFoundError,
    SEConfig,
    TaskKind,
    TaskStatus,
    UnauthorizedError,
    ValidationError,
)
from .repository import SoftwareRepository

logger = logging.getLogger("mio.domain.software_engineering")

_BLOCKING_ISSUE_KINDS = {"placeholder", "stub", "syntax_error"}


class SoftwareEngineeringDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: SoftwareRepository, *, bus=None,
                 config: Optional[SEConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or SEConfig()
        self._metrics = {"analyses": 0, "gates_passed": 0, "gates_failed": 0,
                         "artifacts": 0, "tasks": 0}

    # ------------------------------------------------------------------ #
    def analyze_code(self, actor: str, source: str, *, language: str = "python") -> dict[str, Any]:
        """Deterministik statik analiz raporu (metrikler + issue'lar)."""
        self._authorize(actor)
        report = analyze(source, language=language)
        self._metrics["analyses"] += 1
        self._emit(SEEvents.ANALYZED, {"actor": actor, "language": language,
                                       "issues": report["issue_count"]})
        return report

    def quality_gate(self, actor: str, source: str, *, language: str = "python") -> dict[str, Any]:
        """Anayasa quality gate: placeholder/stub/TODO/syntax hatası → REDDET (deterministik)."""
        self._authorize(actor)
        report = analyze(source, language=language)
        blocking = [i for i in report["issues"] if i["kind"] in _BLOCKING_ISSUE_KINDS]
        passed = not blocking
        self._metrics["gates_passed" if passed else "gates_failed"] += 1
        self._emit(SEEvents.QUALITY_GATE, {"actor": actor, "passed": passed, "blocking": len(blocking)})
        return {"passed": passed, "blocking_issues": blocking, "report": report,
                "verdict": "pass" if passed else "reject"}

    # ------------------------------------------------------------------ #
    def register_artifact(self, actor: str, path: str, *, kind: str = "module",
                          language: str = "python", description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        path = self._require(path, "artefakt yolu")
        art = Artifact(path=path, kind=kind, language=language, description=description)
        self._repo.put_artifact(art)
        self._metrics["artifacts"] += 1
        self._emit(SEEvents.ARTIFACT_REGISTERED, {"actor": actor, "id": art.id, "path": path})
        return art.to_dict()

    def create_task(self, actor: str, title: str, *, kind: str = TaskKind.FEATURE,
                    detail: str = "", artifact_id: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        title = self._require(title, "görev başlığı")
        if kind not in TaskKind.ALL:
            raise ValidationError(f"Geçersiz görev türü: {kind}")
        if artifact_id and self._repo.get_artifact(artifact_id) is None:
            raise NotFoundError(f"Artefakt bulunamadı: {artifact_id}")
        task = EngTask(title=title, kind=kind, detail=detail, artifact_id=artifact_id)
        self._repo.put_task(task)
        self._metrics["tasks"] += 1
        self._emit(SEEvents.TASK_CREATED, {"actor": actor, "id": task.id, "kind": kind})
        return task.to_dict()

    def update_task_status(self, actor: str, task_id: str, status: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        if status not in TaskStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        task = self._repo.get_task(task_id)
        if task is None:
            raise NotFoundError(f"Görev bulunamadı: {task_id}")
        task.status = status
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._repo.put_task(task)
        self._emit(SEEvents.TASK_UPDATED, {"id": task_id, "status": status})
        return task.to_dict()

    def list_tasks(self, actor: str, *, status: Optional[str] = None,
                   kind: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in TaskStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [t.to_dict() for t in self._repo.list_tasks(status=status, kind=kind)]

    def list_artifacts(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [a.to_dict() for a in self._repo.all_artifacts()]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"artifacts": self._repo.artifact_count(), "tasks": self._repo.task_count(),
                "open_tasks": self._repo.task_count(status=TaskStatus.OPEN),
                "done_tasks": self._repo.task_count(status=TaskStatus.DONE),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return software_contract()

    # ------------------------------------------------------------------ #
    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' yazılım-mühendisliği erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' yazma için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
