"""MIO Core · Multi-Agent Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

**Anayasa: Executive tek karar vericidir; agent'lar deterministik atamayla İŞ YÜRÜTÜR, tek başına KARAR VERMEZ.**
Çekirdek: agent registry (rol/yetenek/güven/kapasite) + **deterministik görev atama politikası** (yetenek eşleşmesi
+ güven + boş kapasite) + koordinasyon durum makinesi (pending→assigned→working→completed/failed/**no_agent**/
**no_connector**/**requires_approval**). Gerçek uzak agent çağrısı enjekte edilen executor adapter'a (DI) delege;
yoksa DÜRÜSTÇE no_connector (uydurma sonuç YOK — Madde 8). Yüksek-risk/geri-alınamaz görev ONAY ister (Madde 24).
Gerçek uzak yürütme çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentStatus:
    ACTIVE = "active"
    PAUSED = "paused"           # atama dışı
    ALL = {ACTIVE, PAUSED}


class Risk:
    LOW = "low"
    HIGH = "high"              # geri-alınamaz/dış etkili → onay şart


class TaskStatus:
    PENDING = "pending"
    ASSIGNED = "assigned"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_AGENT = "no_agent"           # uygun agent yok (dürüst)
    NO_CONNECTOR = "no_connector"   # agent atandı ama gerçek executor bağlı değil (dürüst)
    REQUIRES_APPROVAL = "requires_approval"   # yüksek-risk, onay bekliyor (Madde 24)
    ALL = {PENDING, ASSIGNED, WORKING, COMPLETED, FAILED, NO_AGENT, NO_CONNECTOR, REQUIRES_APPROVAL}
    # atanan agent'ın "yükü" sayılan aktif durumlar
    ACTIVE_LOAD = {ASSIGNED, WORKING}


# Deterministik yüksek-risk görev işaretleri (geri-alınamaz/dış etkili)
HIGH_RISK_MARKERS = ("delete", "deploy", "publish", "transfer", "pay", "purchase", "shutdown", "release",
                     "sil", "yayınla", "gönder", "öde", "dağıt", "devreye al")


class MultiAgentError(Exception):
    """Multi-Agent Domain temel hatası."""


class ValidationError(MultiAgentError):
    pass


class UnauthorizedError(MultiAgentError):
    pass


class NotFoundError(MultiAgentError):
    pass


def classify_risk(title: str, declared: str = Risk.LOW) -> str:
    """Deterministik risk: bildirilen 'high' ise ya da başlık tehlikeli işaret içeriyorsa → high."""
    t = (title or "").lower()
    if declared == Risk.HIGH or any(m in t for m in HIGH_RISK_MARKERS):
        return Risk.HIGH
    return Risk.LOW


@dataclass
class Agent:
    name: str
    role: str = "worker"
    capabilities: list = field(default_factory=list)
    trust: float = 0.5             # 0..1 (deterministik atamada tercih)
    max_load: int = 1             # eşzamanlı görev kapasitesi
    status: str = AgentStatus.ACTIVE
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "role": self.role,
                "capabilities": list(self.capabilities), "trust": self.trust, "max_load": self.max_load,
                "status": self.status, "description": self.description, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Agent":
        return cls(name=d["name"], role=d.get("role", "worker"),
                   capabilities=list(d.get("capabilities") or []), trust=float(d.get("trust", 0.5)),
                   max_load=int(d.get("max_load", 1)), status=d.get("status", AgentStatus.ACTIVE),
                   description=d.get("description", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class AgentTask:
    title: str
    required_capabilities: list = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    priority: int = 100
    risk: str = Risk.LOW
    status: str = TaskStatus.PENDING
    assigned_agent: str = ""
    result: dict = field(default_factory=dict)
    error: str = ""
    connector: str = ""
    approved_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title,
                "required_capabilities": list(self.required_capabilities), "payload": self.payload,
                "priority": self.priority, "risk": self.risk, "status": self.status,
                "assigned_agent": self.assigned_agent, "result": self.result, "error": self.error,
                "connector": self.connector, "approved_by": self.approved_by,
                "created_at": self.created_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentTask":
        return cls(title=d["title"], required_capabilities=list(d.get("required_capabilities") or []),
                   payload=dict(d.get("payload") or {}), priority=int(d.get("priority", 100)),
                   risk=d.get("risk", Risk.LOW), status=d.get("status", TaskStatus.PENDING),
                   assigned_agent=d.get("assigned_agent", ""), result=dict(d.get("result") or {}),
                   error=d.get("error", ""), connector=d.get("connector", ""),
                   approved_by=d.get("approved_by", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), finished_at=d.get("finished_at"))


def assignment_score(agent: Agent, spare: int) -> tuple:
    """Deterministik atama skoru (LLM'siz): trust↑, boş kapasite↑, name (kararlı tie-break)."""
    return (agent.trust, spare, agent.name)


@dataclass
class MultiAgentConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Planning", "Reasoning", "Perception"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Planning"})
    # Madde 24: yüksek-risk görevi yalnız bunlar onaylayabilir
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "AgentStatus", "Risk", "TaskStatus", "HIGH_RISK_MARKERS", "classify_risk", "Agent", "AgentTask",
    "assignment_score", "MultiAgentConfig",
    "MultiAgentError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
