"""MIO Core · Multi-Agent Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

**Anayasa: Executive tek karar vericidir; agent'lar deterministik atamayla İŞ YÜRÜTÜR, tek başına KARAR VERMEZ.**
Agent registry + **deterministik görev atama** (yetenek eşleşmesi + güven + boş kapasite) + koordinasyon durum
makinesi. Gerçek uzak agent çağrısı enjekte edilen executor adapter'a (DI) delege; uygun agent yoksa **no_agent**,
executor yoksa **no_connector** (uydurma sonuç YOK — Madde 8). Yüksek-risk/geri-alınamaz görev ONAY ister
(Madde 24). Gerçek uzak yürütme çekirdekte YOK. authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, MultiAgentEvents, multi_agent_contract
from .models import (
    Agent,
    AgentStatus,
    AgentTask,
    MultiAgentConfig,
    NotFoundError,
    Risk,
    TaskStatus,
    UnauthorizedError,
    ValidationError,
    assignment_score,
    classify_risk,
)
from .repository import MultiAgentRepository

logger = logging.getLogger("mio.domain.multi_agent")

Executor = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MultiAgentDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: MultiAgentRepository, *, bus=None,
                 config: Optional[MultiAgentConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or MultiAgentConfig()
        self._executors: dict[str, tuple[Executor, str]] = {}   # agent_id -> (fn, adapter adı)
        self._metrics = {"agents": 0, "tasks": 0, "assigned": 0, "completed": 0, "no_agent": 0,
                         "no_connector": 0, "failed": 0, "approval_required": 0}

    # ------------------------------------------------------------------ #
    def register_executor(self, agent_id: str, fn: Executor, *, name: str = "adapter") -> None:
        """Bir agent için GERÇEK uzak yürütme connector'ı bağlar (kompozisyon-zamanı DI)."""
        if self._repo.get_agent(agent_id) is None:
            raise NotFoundError(f"Agent bulunamadı: {agent_id}")
        self._executors[agent_id] = (fn, name)

    def register_agent(self, actor: str, name: str, *, role: str = "worker",
                       capabilities: Optional[list] = None, trust: float = 0.5, max_load: int = 1,
                       status: str = AgentStatus.ACTIVE, description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "agent adı")
        if status not in AgentStatus.ALL:
            raise ValidationError(f"Geçersiz agent durumu: {status}")
        if not (0.0 <= float(trust) <= 1.0):
            raise ValidationError("trust 0..1 aralığında olmalı")
        if int(max_load) < 1:
            raise ValidationError("max_load >= 1 olmalı")
        a = Agent(name=name, role=role, capabilities=list(capabilities or []), trust=float(trust),
                  max_load=int(max_load), status=status, description=description)
        self._repo.put_agent(a)
        self._metrics["agents"] += 1
        self._emit(MultiAgentEvents.AGENT_REGISTERED, {"actor": actor, "id": a.id, "role": role})
        return a.to_dict()

    def submit_task(self, actor: str, title: str, *, required_capabilities: Optional[list] = None,
                    payload: Optional[dict] = None, priority: int = 100, risk: str = Risk.LOW,
                    user_approved: bool = False) -> dict[str, Any]:
        """Görev oluşturur. Yüksek-risk + onaysız → requires_approval (Madde 24); aksi → deterministik ata+yürüt."""
        self._authorize_writer(actor)
        title = self._require(title, "görev başlığı")
        eff_risk = classify_risk(title, risk)
        task = AgentTask(title=title, required_capabilities=list(required_capabilities or []),
                         payload=dict(payload or {}), priority=int(priority), risk=eff_risk,
                         status=TaskStatus.PENDING)
        self._metrics["tasks"] += 1
        self._emit(MultiAgentEvents.TASK_SUBMITTED, {"id": task.id, "risk": eff_risk})

        if eff_risk == Risk.HIGH and not user_approved:      # Madde 24: onaysız çalışmaz
            task.status = TaskStatus.REQUIRES_APPROVAL
            self._repo.put_task(task)
            self._metrics["approval_required"] += 1
            self._emit(MultiAgentEvents.APPROVAL_REQUIRED, {"id": task.id, "title": title})
            return task.to_dict()
        return self._assign_and_dispatch(task)

    def approve_task(self, actor: str, task_id: str) -> dict[str, Any]:
        """Onay bekleyen yüksek-risk görevi onaylar ve yürütür (yalnız approver — Madde 24)."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' yüksek-risk görev onaylayamaz (Madde 24)")
        task = self._repo.get_task(task_id)
        if task is None:
            raise NotFoundError(f"Görev bulunamadı: {task_id}")
        if task.status != TaskStatus.REQUIRES_APPROVAL:
            raise ValidationError(f"Yalnız 'requires_approval' onaylanır (durum: {task.status})")
        task.approved_by = actor
        self._emit(MultiAgentEvents.APPROVED, {"id": task_id, "by": actor})
        return self._assign_and_dispatch(task)

    # ------------------------------------------------------------------ #
    def _eligible(self, required: list) -> list[tuple[Agent, int]]:
        """Yetenek ⊇ gerekli + boş kapasitesi olan ACTIVE agent'lar (agent, spare)."""
        need = set(required or [])
        out: list[tuple[Agent, int]] = []
        for a in self._repo.all_agents():
            if a.status != AgentStatus.ACTIVE:
                continue
            if not need.issubset(set(a.capabilities)):
                continue
            spare = a.max_load - self._repo.active_load(a.id)
            if spare > 0:
                out.append((a, spare))
        return out

    def _assign_and_dispatch(self, task: AgentTask) -> dict[str, Any]:
        eligible = self._eligible(task.required_capabilities)
        if not eligible:                        # DÜRÜST: uygun agent yok
            task.status = TaskStatus.NO_AGENT
            task.finished_at = _now()
            self._repo.put_task(task)
            self._metrics["no_agent"] += 1
            self._emit(MultiAgentEvents.NO_AGENT, {"id": task.id,
                       "required": list(task.required_capabilities)})
            return task.to_dict()
        agent, spare = max(eligible, key=lambda pair: assignment_score(pair[0], pair[1]))
        task.assigned_agent = agent.id
        task.status = TaskStatus.ASSIGNED
        self._repo.put_task(task)
        self._metrics["assigned"] += 1
        self._emit(MultiAgentEvents.TASK_ASSIGNED, {"id": task.id, "agent": agent.id, "agent_name": agent.name})
        return self._dispatch(task, agent)

    def _dispatch(self, task: AgentTask, agent: Agent) -> dict[str, Any]:
        entry = self._executors.get(agent.id)
        if entry is None:                       # DÜRÜST: gerçek uzak executor bağlı değil
            task.status = TaskStatus.NO_CONNECTOR
            task.finished_at = _now()
            self._repo.put_task(task)
            self._metrics["no_connector"] += 1
            self._emit(MultiAgentEvents.NO_CONNECTOR, {"id": task.id, "agent": agent.id})
            return task.to_dict()
        fn, name = entry
        task.connector = name
        task.status = TaskStatus.WORKING
        self._repo.put_task(task)
        try:
            result = fn({"task": task.to_dict(), "agent": agent.to_dict()})
            task.status = TaskStatus.COMPLETED
            task.result = dict(result or {})
            self._metrics["completed"] += 1
            self._emit(MultiAgentEvents.TASK_COMPLETED, {"id": task.id, "agent": agent.id})
        except Exception as exc:  # noqa: BLE001 — executor hatası göreve dönüşür, sistemi bozmaz
            task.status = TaskStatus.FAILED
            task.error = str(exc)[:300]
            self._metrics["failed"] += 1
            self._emit(MultiAgentEvents.TASK_FAILED, {"id": task.id, "error": task.error})
        task.finished_at = _now()
        self._repo.put_task(task)
        return task.to_dict()

    # -- sorgular -------------------------------------------------------- #
    def get_task(self, actor: str, task_id: str) -> dict[str, Any]:
        self._authorize(actor)
        t = self._repo.get_task(task_id)
        if t is None:
            raise NotFoundError(f"Görev bulunamadı: {task_id}")
        return t.to_dict()

    def list_tasks(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in TaskStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [t.to_dict() for t in self._repo.all_tasks(status=status)]

    def list_agents(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [a.to_dict() for a in self._repo.all_agents()]

    def eligible_agents(self, actor: str, required_capabilities: Optional[list] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [{**a.to_dict(), "spare": spare}
                for a, spare in self._eligible(required_capabilities or [])]

    def executors(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"bound_agents": sorted(self._executors)}

    def stats(self) -> dict[str, Any]:
        return {"agents": self._repo.agent_count(), "tasks": self._repo.task_count(),
                "pending_approval": self._repo.task_count(status=TaskStatus.REQUIRES_APPROVAL),
                "executors": len(self._executors), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return multi_agent_contract()

    # ------------------------------------------------------------------ #
    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' multi-agent erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' agent/görev yönetimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
