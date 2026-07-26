"""MIO Core · Distributed Execution Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

**Anayasa: Execution tek başına karar vermez; dağıtım DETERMİNİSTİK politikadır; yüksek-risk/geri-alınamaz dağıtık
iş ONAY ister (Madde 24).** Çekirdek: çalışma düğümü (worker node) registry (kapasite/yetenek/sağlık) +
**deterministik iş dağıtım/zamanlama** (yetenek eşleşmesi + kapasite + öncelik) + dağıtık iş durum makinesi
(queued→scheduled→running→completed/failed/**no_node**/**no_connector**/**requires_approval**) + **idempotency**
(deterministik iş kimliğiyle effectively-once). Gerçek uzak çalıştırma enjekte edilen node executor adapter'a (DI)
delege; düğüm yoksa no_node, executor yoksa no_connector (uydurma sonuç YOK — Madde 8). Gerçek uzak yürütme
çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NodeStatus:
    HEALTHY = "healthy"         # iş alabilir
    DRAINING = "draining"       # yeni iş almaz (mevcut biter)
    DOWN = "down"              # kullanım dışı
    ALL = {HEALTHY, DRAINING, DOWN}


class Risk:
    LOW = "low"
    HIGH = "high"              # geri-alınamaz dağıtık iş → onay şart


class JobStatus:
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_NODE = "no_node"             # uygun düğüm yok (dürüst)
    NO_CONNECTOR = "no_connector"   # düğüm atandı ama gerçek executor bağlı değil (dürüst)
    REQUIRES_APPROVAL = "requires_approval"   # yüksek-risk, onay bekliyor (Madde 24)
    ALL = {QUEUED, SCHEDULED, RUNNING, COMPLETED, FAILED, NO_NODE, NO_CONNECTOR, REQUIRES_APPROVAL}
    ACTIVE_LOAD = {SCHEDULED, RUNNING}   # düğüm kapasitesini tüketen durumlar
    # idempotency: bu durumdaki bir iş 'canlı/başarılı' sayılır (dedup) — FAILED tekrar denenebilir
    LIVE = {QUEUED, SCHEDULED, RUNNING, COMPLETED, NO_CONNECTOR, REQUIRES_APPROVAL}


# Deterministik yüksek-risk dağıtık iş işaretleri (geri-alınamaz/yıkıcı)
HIGH_RISK_MARKERS = ("delete", "drop", "destroy", "migrate", "truncate", "wipe", "purge",
                     "sil", "taşı", "yok et", "biçimlendir")


class DistExecError(Exception):
    """Distributed Execution Domain temel hatası."""


class ValidationError(DistExecError):
    pass


class UnauthorizedError(DistExecError):
    pass


class NotFoundError(DistExecError):
    pass


def classify_risk(task: str, declared: str = Risk.LOW) -> str:
    """Deterministik risk: bildirilen 'high' ise ya da görev tehlikeli işaret içeriyorsa → high."""
    t = (task or "").lower()
    if declared == Risk.HIGH or any(m in t for m in HIGH_RISK_MARKERS):
        return Risk.HIGH
    return Risk.LOW


@dataclass
class Node:
    name: str
    capabilities: list = field(default_factory=list)
    capacity: int = 1              # eşzamanlı iş slotu
    status: str = NodeStatus.HEALTHY
    region: str = ""
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "capabilities": list(self.capabilities),
                "capacity": self.capacity, "status": self.status, "region": self.region,
                "description": self.description, "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Node":
        return cls(name=d["name"], capabilities=list(d.get("capabilities") or []),
                   capacity=int(d.get("capacity", 1)), status=d.get("status", NodeStatus.HEALTHY),
                   region=d.get("region", ""), description=d.get("description", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   updated_at=d.get("updated_at") or _now())


@dataclass
class DistributedJob:
    task: str
    required_capabilities: list = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    priority: int = 100
    risk: str = Risk.LOW
    idempotency_key: str = ""
    status: str = JobStatus.QUEUED
    assigned_node: str = ""
    result: dict = field(default_factory=dict)
    error: str = ""
    connector: str = ""
    approved_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "task": self.task,
                "required_capabilities": list(self.required_capabilities), "payload": self.payload,
                "priority": self.priority, "risk": self.risk, "idempotency_key": self.idempotency_key,
                "status": self.status, "assigned_node": self.assigned_node, "result": self.result,
                "error": self.error, "connector": self.connector, "approved_by": self.approved_by,
                "created_at": self.created_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DistributedJob":
        return cls(task=d["task"], required_capabilities=list(d.get("required_capabilities") or []),
                   payload=dict(d.get("payload") or {}), priority=int(d.get("priority", 100)),
                   risk=d.get("risk", Risk.LOW), idempotency_key=d.get("idempotency_key", ""),
                   status=d.get("status", JobStatus.QUEUED), assigned_node=d.get("assigned_node", ""),
                   result=dict(d.get("result") or {}), error=d.get("error", ""),
                   connector=d.get("connector", ""), approved_by=d.get("approved_by", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   finished_at=d.get("finished_at"))


def schedule_score(node: Node, spare: int) -> tuple:
    """Deterministik zamanlama skoru (LLM'siz): en boş düğüm (spare↑), sonra name (kararlı tie-break)."""
    return (spare, node.name)


@dataclass
class DistExecConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Planning", "Scheduler", "Execution"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Scheduler"})
    # Madde 24: yüksek-risk dağıtık işi yalnız bunlar onaylayabilir
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "NodeStatus", "Risk", "JobStatus", "HIGH_RISK_MARKERS", "classify_risk", "Node", "DistributedJob",
    "schedule_score", "DistExecConfig",
    "DistExecError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
