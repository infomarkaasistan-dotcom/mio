"""MIO Core · Distributed Execution Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

**Anayasa: Execution tek başına karar vermez; dağıtım DETERMİNİSTİK; yüksek-risk dağıtık iş ONAY ister (Madde 24).**
Worker node registry + **deterministik iş dağıtım/zamanlama** (yetenek + kapasite + öncelik) + dağıtık iş durum
makinesi + **idempotency** (effectively-once). Gerçek uzak çalıştırma enjekte edilen node executor adapter'a (DI)
delege; uygun düğüm yoksa **no_node**, executor yoksa **no_connector** (uydurma sonuç YOK — Madde 8). Gerçek uzak
yürütme çekirdekte YOK. authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, DistExecEvents, dist_exec_contract
from .models import (
    DistExecConfig,
    DistributedJob,
    JobStatus,
    Node,
    NodeStatus,
    NotFoundError,
    Risk,
    UnauthorizedError,
    ValidationError,
    classify_risk,
    schedule_score,
)
from .repository import DistExecRepository

logger = logging.getLogger("mio.domain.distributed_execution")

Executor = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DistributedExecutionDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: DistExecRepository, *, bus=None,
                 config: Optional[DistExecConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or DistExecConfig()
        self._executors: dict[str, tuple[Executor, str]] = {}   # node_id -> (fn, adapter adı)
        self._metrics = {"nodes": 0, "jobs": 0, "deduped": 0, "scheduled": 0, "completed": 0,
                         "no_node": 0, "no_connector": 0, "failed": 0, "approval_required": 0}

    # ------------------------------------------------------------------ #
    def register_executor(self, node_id: str, fn: Executor, *, name: str = "adapter") -> None:
        """Bir düğüm için GERÇEK uzak çalıştırma connector'ı bağlar (kompozisyon-zamanı DI)."""
        if self._repo.get_node(node_id) is None:
            raise NotFoundError(f"Düğüm bulunamadı: {node_id}")
        self._executors[node_id] = (fn, name)

    def register_node(self, actor: str, name: str, *, capabilities: Optional[list] = None,
                      capacity: int = 1, status: str = NodeStatus.HEALTHY, region: str = "",
                      description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "düğüm adı")
        if status not in NodeStatus.ALL:
            raise ValidationError(f"Geçersiz düğüm durumu: {status}")
        if int(capacity) < 1:
            raise ValidationError("capacity >= 1 olmalı")
        n = Node(name=name, capabilities=list(capabilities or []), capacity=int(capacity), status=status,
                 region=region, description=description)
        self._repo.put_node(n)
        self._metrics["nodes"] += 1
        self._emit(DistExecEvents.NODE_REGISTERED, {"actor": actor, "id": n.id})
        return n.to_dict()

    def set_node_status(self, actor: str, node_id: str, status: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        if status not in NodeStatus.ALL:
            raise ValidationError(f"Geçersiz düğüm durumu: {status}")
        n = self._require_node(node_id)
        n.status = status
        n.updated_at = _now()
        self._repo.put_node(n)
        self._emit(DistExecEvents.NODE_STATUS_CHANGED, {"id": n.id, "status": status})
        return n.to_dict()

    def submit(self, actor: str, task: str, *, required_capabilities: Optional[list] = None,
               payload: Optional[dict] = None, priority: int = 100, risk: str = Risk.LOW,
               idempotency_key: str = "", user_approved: bool = False) -> dict[str, Any]:
        """İş gönderir. idempotency_key ile effectively-once. Yüksek-risk+onaysız → requires_approval (Madde 24)."""
        self._authorize_writer(actor)
        task = self._require(task, "görev")
        if idempotency_key:                      # effectively-once: canlı/başarılı iş varsa tekrarlama
            for existing in self._repo.find_by_idempotency(idempotency_key):
                if existing.status in JobStatus.LIVE:
                    self._metrics["deduped"] += 1
                    self._emit(DistExecEvents.JOB_DEDUPED, {"id": existing.id, "key": idempotency_key})
                    return existing.to_dict()
        eff_risk = classify_risk(task, risk)
        job = DistributedJob(task=task, required_capabilities=list(required_capabilities or []),
                             payload=dict(payload or {}), priority=int(priority), risk=eff_risk,
                             idempotency_key=idempotency_key, status=JobStatus.QUEUED)
        self._metrics["jobs"] += 1
        self._emit(DistExecEvents.JOB_SUBMITTED, {"id": job.id, "risk": eff_risk})

        if eff_risk == Risk.HIGH and not user_approved:      # Madde 24: onaysız çalışmaz
            job.status = JobStatus.REQUIRES_APPROVAL
            self._repo.put_job(job)
            self._metrics["approval_required"] += 1
            self._emit(DistExecEvents.APPROVAL_REQUIRED, {"id": job.id, "task": task})
            return job.to_dict()
        return self._schedule_and_dispatch(job)

    def approve_job(self, actor: str, job_id: str) -> dict[str, Any]:
        """Onay bekleyen yüksek-risk işi onaylar ve dağıtır (yalnız approver — Madde 24)."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' yüksek-risk dağıtık iş onaylayamaz (Madde 24)")
        job = self._repo.get_job(job_id)
        if job is None:
            raise NotFoundError(f"İş bulunamadı: {job_id}")
        if job.status != JobStatus.REQUIRES_APPROVAL:
            raise ValidationError(f"Yalnız 'requires_approval' onaylanır (durum: {job.status})")
        job.approved_by = actor
        self._emit(DistExecEvents.APPROVED, {"id": job_id, "by": actor})
        return self._schedule_and_dispatch(job)

    # ------------------------------------------------------------------ #
    def _eligible(self, required: list) -> list[tuple[Node, int]]:
        """HEALTHY + yetenek ⊇ gerekli + boş kapasitesi olan düğümler (node, spare)."""
        need = set(required or [])
        out: list[tuple[Node, int]] = []
        for n in self._repo.all_nodes():
            if n.status != NodeStatus.HEALTHY:
                continue
            if not need.issubset(set(n.capabilities)):
                continue
            spare = n.capacity - self._repo.active_load(n.id)
            if spare > 0:
                out.append((n, spare))
        return out

    def _schedule_and_dispatch(self, job: DistributedJob) -> dict[str, Any]:
        eligible = self._eligible(job.required_capabilities)
        if not eligible:                        # DÜRÜST: uygun düğüm yok
            job.status = JobStatus.NO_NODE
            job.finished_at = _now()
            self._repo.put_job(job)
            self._metrics["no_node"] += 1
            self._emit(DistExecEvents.NO_NODE, {"id": job.id,
                       "required": list(job.required_capabilities)})
            return job.to_dict()
        node, spare = max(eligible, key=lambda pair: schedule_score(pair[0], pair[1]))
        job.assigned_node = node.id
        job.status = JobStatus.SCHEDULED
        self._repo.put_job(job)
        self._metrics["scheduled"] += 1
        self._emit(DistExecEvents.JOB_SCHEDULED, {"id": job.id, "node": node.id, "node_name": node.name})
        return self._dispatch(job, node)

    def _dispatch(self, job: DistributedJob, node: Node) -> dict[str, Any]:
        entry = self._executors.get(node.id)
        if entry is None:                       # DÜRÜST: gerçek uzak executor bağlı değil
            job.status = JobStatus.NO_CONNECTOR
            job.finished_at = _now()
            self._repo.put_job(job)
            self._metrics["no_connector"] += 1
            self._emit(DistExecEvents.NO_CONNECTOR, {"id": job.id, "node": node.id})
            return job.to_dict()
        fn, name = entry
        job.connector = name
        job.status = JobStatus.RUNNING
        self._repo.put_job(job)
        try:
            result = fn({"job": job.to_dict(), "node": node.to_dict()})
            job.status = JobStatus.COMPLETED
            job.result = dict(result or {})
            self._metrics["completed"] += 1
            self._emit(DistExecEvents.JOB_COMPLETED, {"id": job.id, "node": node.id})
        except Exception as exc:  # noqa: BLE001 — executor hatası işe dönüşür, sistemi bozmaz
            job.status = JobStatus.FAILED
            job.error = str(exc)[:300]
            self._metrics["failed"] += 1
            self._emit(DistExecEvents.JOB_FAILED, {"id": job.id, "error": job.error})
        job.finished_at = _now()
        self._repo.put_job(job)
        return job.to_dict()

    # -- sorgular -------------------------------------------------------- #
    def get_job(self, actor: str, job_id: str) -> dict[str, Any]:
        self._authorize(actor)
        j = self._repo.get_job(job_id)
        if j is None:
            raise NotFoundError(f"İş bulunamadı: {job_id}")
        return j.to_dict()

    def list_jobs(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in JobStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [j.to_dict() for j in self._repo.all_jobs(status=status)]

    def list_nodes(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [n.to_dict() for n in self._repo.all_nodes()]

    def eligible_nodes(self, actor: str, required_capabilities: Optional[list] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [{**n.to_dict(), "spare": spare}
                for n, spare in self._eligible(required_capabilities or [])]

    def executors(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"bound_nodes": sorted(self._executors)}

    def stats(self) -> dict[str, Any]:
        return {"nodes": self._repo.node_count(), "jobs": self._repo.job_count(),
                "pending_approval": self._repo.job_count(status=JobStatus.REQUIRES_APPROVAL),
                "executors": len(self._executors), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return dist_exec_contract()

    # ------------------------------------------------------------------ #
    def _require_node(self, node_id: str) -> Node:
        n = self._repo.get_node(node_id)
        if n is None:
            raise NotFoundError(f"Düğüm bulunamadı: {node_id}")
        return n

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' dağıtık yürütme erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' düğüm/iş yönetimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
