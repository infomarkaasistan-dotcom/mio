"""MIO Core · Workflow Domain Service (production-grade), LLM-BAĞIMSIZ, DETERMİNİSTİK.

Görev grafı (DAG) yürütme: bağımlılık çözümü + checkpoint/resume + human-approval + rollback. **Domain
ConnectorManager çağırmaz**; her görev bir CapabilityIntent taşır — yürütmeye EXECUTIVE karar verir. Human-approval
görevi onaysız yürütülmez (Madde 24). authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contract import CONTRACT_VERSION, WorkflowEvents, workflow_contract
from .models import (
    NotFoundError,
    TaskStatus,
    UnauthorizedError,
    ValidationError,
    Workflow,
    WorkflowConfig,
    WorkflowStatus,
    WorkflowTask,
    topological_order,
    validate_dag,
)
from .repository import WorkflowRepository

logger = logging.getLogger("mio.domain.workflow")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: WorkflowRepository, *, bus=None,
                 config: Optional[WorkflowConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or WorkflowConfig()
        self._metrics = {"workflows": 0, "tasks_completed": 0, "tasks_failed": 0, "approvals_required": 0,
                         "rollbacks": 0}

    # -- oluşturma (DAG doğrulama) -------------------------------------- #
    def create_workflow(self, actor: str, name: str, tasks: list) -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "workflow adı")
        if not isinstance(tasks, list) or not tasks:
            raise ValidationError("en az bir görev gerekli")
        wtasks = [WorkflowTask.from_dict(t) if isinstance(t, dict) else t for t in tasks]
        validate_dag(wtasks)                          # döngü/eksik bağımlılık → DAGError
        wf = Workflow(name=name, tasks=wtasks, status=WorkflowStatus.DRAFT)
        self._recompute_ready(wf)
        self._repo.put(wf)
        self._metrics["workflows"] += 1
        self._emit(WorkflowEvents.CREATED, {"actor": actor, "id": wf.id, "tasks": len(wtasks)})
        return wf.to_dict()

    def start(self, actor: str, workflow_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        wf = self._require(workflow_id and self._repo.get(workflow_id), f"Workflow bulunamadı: {workflow_id}",
                           is_obj=True)
        wf.status = WorkflowStatus.RUNNING
        self._recompute_ready(wf)
        wf.updated_at = _now()
        self._repo.put(wf)
        self._emit(WorkflowEvents.STARTED, {"id": wf.id})
        return wf.to_dict()

    # -- yürütme durumu (checkpoint) ------------------------------------ #
    def ready_tasks(self, actor: str, workflow_id: str) -> list[dict[str, Any]]:
        """Çalıştırılabilir görevler — bağımlılıkları tamam, onay engeli yok. Executive bunları yürütür."""
        self._authorize(actor)
        wf = self._get(workflow_id)
        self._recompute_ready(wf)
        self._repo.put(wf)
        return [t.to_dict() for t in wf.tasks if t.status == TaskStatus.READY]

    def complete_task(self, actor: str, workflow_id: str, task_id: str, *,
                      result: Optional[dict] = None) -> dict[str, Any]:
        """Görevi tamamlar (checkpoint). Sonraki görevler otomatik ready olur. Executive'in yürütme sonrası çağrısı."""
        self._authorize_writer(actor)
        wf = self._get(workflow_id)
        task = self._get_task(wf, task_id)
        if task.status not in (TaskStatus.READY, TaskStatus.RUNNING):
            raise ValidationError(f"Yalnız ready/running görev tamamlanır (durum: {task.status})")
        task.status = TaskStatus.COMPLETED
        task.result = dict(result or {})
        self._metrics["tasks_completed"] += 1
        self._emit(WorkflowEvents.TASK_COMPLETED, {"id": wf.id, "task": task.name})
        self._recompute_ready(wf)
        self._finalize_if_done(wf)
        wf.updated_at = _now()
        self._repo.put(wf)
        return wf.to_dict()

    def fail_task(self, actor: str, workflow_id: str, task_id: str, *, error: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        wf = self._get(workflow_id)
        task = self._get_task(wf, task_id)
        task.status = TaskStatus.FAILED
        task.error = (error or "")[:300]
        wf.status = WorkflowStatus.FAILED
        self._metrics["tasks_failed"] += 1
        self._emit(WorkflowEvents.TASK_FAILED, {"id": wf.id, "task": task.name, "error": task.error})
        self._emit(WorkflowEvents.FAILED, {"id": wf.id})
        wf.updated_at = _now()
        self._repo.put(wf)
        return wf.to_dict()

    def approve_task(self, actor: str, workflow_id: str, task_id: str) -> dict[str, Any]:
        """Human-approval görevini onaylar → ready (Madde 24; yalnız approver)."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' görev onaylayamaz (Madde 24)")
        wf = self._get(workflow_id)
        task = self._get_task(wf, task_id)
        if task.status != TaskStatus.BLOCKED_APPROVAL:
            raise ValidationError(f"Yalnız 'blocked_approval' onaylanır (durum: {task.status})")
        task.requires_approval = False               # onaylandı
        self._recompute_ready(wf)
        wf.updated_at = _now()
        self._repo.put(wf)
        return wf.to_dict()

    def rollback(self, actor: str, workflow_id: str, task_id: str) -> dict[str, Any]:
        """Bir görevi + TÜM ardıllarını (descendant) pending yapar (deterministik). Checkpoint geri sarma."""
        self._authorize_writer(actor)
        wf = self._get(workflow_id)
        target = self._get_task(wf, task_id)
        affected = self._descendants(wf, target.name) | {target.name}
        for t in wf.tasks:
            if t.name in affected:
                t.status = TaskStatus.PENDING
                t.result = {}
                t.error = ""
        wf.status = WorkflowStatus.RUNNING
        self._recompute_ready(wf)
        self._metrics["rollbacks"] += 1
        self._emit(WorkflowEvents.ROLLED_BACK, {"id": wf.id, "from": target.name,
                   "affected": sorted(affected)})
        wf.updated_at = _now()
        self._repo.put(wf)
        return wf.to_dict()

    def plan(self, actor: str, workflow_id: str) -> dict[str, Any]:
        """Deterministik yürütme planı: topolojik sıra + her görevin CapabilityIntent'i (yürütme YOK)."""
        self._authorize(actor)
        wf = self._get(workflow_id)
        order = topological_order(wf.tasks)
        by_name = {t.name: t for t in wf.tasks}
        steps = []
        for name in order:
            t = by_name[name]
            steps.append({"task": t.name, "capability": t.capability, "request": dict(t.request),
                          "requires_approval": t.requires_approval, "status": t.status})
        return {"workflow_id": wf.id, "order": order, "steps": steps}

    # -- sorgular -------------------------------------------------------- #
    def get_workflow(self, actor: str, workflow_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._get(workflow_id).to_dict()

    def list_workflows(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in WorkflowStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [w.to_dict() for w in self._repo.all(status=status)]

    def stats(self) -> dict[str, Any]:
        return {"workflows": self._repo.count(),
                "running": self._repo.count(status=WorkflowStatus.RUNNING),
                "completed": self._repo.count(status=WorkflowStatus.COMPLETED),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return workflow_contract()

    # ------------------------------------------------------------------ #
    def _recompute_ready(self, wf: Workflow) -> None:
        """Deterministik: bağımlılıkları tamamlanan pending görevleri ready (ya da human-approval'sa blocked)."""
        completed = {t.name for t in wf.tasks if t.status == TaskStatus.COMPLETED}
        for t in wf.tasks:
            if t.status not in (TaskStatus.PENDING, TaskStatus.READY, TaskStatus.BLOCKED_APPROVAL):
                continue
            deps_ok = all(d in completed for d in t.depends_on)
            if not deps_ok:
                t.status = TaskStatus.PENDING
            elif t.requires_approval:
                if t.status != TaskStatus.BLOCKED_APPROVAL:
                    self._metrics["approvals_required"] += 1
                    self._emit(WorkflowEvents.APPROVAL_REQUIRED, {"id": wf.id, "task": t.name})
                t.status = TaskStatus.BLOCKED_APPROVAL
            else:
                if t.status == TaskStatus.PENDING:
                    self._emit(WorkflowEvents.TASK_READY, {"id": wf.id, "task": t.name})
                t.status = TaskStatus.READY

    def _finalize_if_done(self, wf: Workflow) -> None:
        if all(t.status in TaskStatus.TERMINAL for t in wf.tasks):
            if any(t.status == TaskStatus.FAILED for t in wf.tasks):
                wf.status = WorkflowStatus.FAILED
                self._emit(WorkflowEvents.FAILED, {"id": wf.id})
            else:
                wf.status = WorkflowStatus.COMPLETED
                self._emit(WorkflowEvents.COMPLETED, {"id": wf.id})

    def _descendants(self, wf: Workflow, name: str) -> set:
        """name'e (dolaylı) bağımlı tüm görevler."""
        dependents: dict[str, list] = {t.name: [] for t in wf.tasks}
        for t in wf.tasks:
            for d in t.depends_on:
                dependents[d].append(t.name)
        seen: set = set()
        stack = list(dependents.get(name, []))
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(dependents.get(n, []))
        return seen

    def _get(self, workflow_id: str) -> Workflow:
        wf = self._repo.get(workflow_id)
        if wf is None:
            raise NotFoundError(f"Workflow bulunamadı: {workflow_id}")
        return wf

    @staticmethod
    def _get_task(wf: Workflow, task_id: str) -> WorkflowTask:
        t = wf.task_by_id(task_id) or wf.task_by_name(task_id)
        if t is None:
            raise NotFoundError(f"Görev bulunamadı: {task_id}")
        return t

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' workflow erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' workflow yazma için yetkili değil")

    @staticmethod
    def _require(value, label: str, *, is_obj: bool = False):
        if is_obj:
            if value is None:
                raise NotFoundError(label)
            return value
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
