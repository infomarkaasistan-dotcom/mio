"""MIO Core · Goal Management Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

E2 GoalManager'ı governance kabuğuyla SARAR (çekirdeğe dokunmadan): hedef→milestone→görev hiyerarşisi,
deterministik ilerleme, E1 senkron. Mutasyonlar GoalManager üzerinden; okumalar paylaşılan GoalStore
üzerinden (tek doğruluk kaynağı). Çekirdeğin ValueError'ları domain hata hiyerarşisine çevrilir.
authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, GoalMgmtEvents, goal_management_contract
from .models import (
    GoalConfig,
    NotFoundError,
    TASK_RESULT_STATUSES,
    UnauthorizedError,
    ValidationError,
)

logger = logging.getLogger("mio.domain.goal_management")


class GoalManagementDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, manager, store, *, bus=None, config: Optional[GoalConfig] = None) -> None:
        self._mgr = manager           # E2 GoalManager (mutasyon + E1 senkron)
        self._store = store           # paylaşılan GoalStore (okuma)
        self._bus = bus
        self._cfg = config or GoalConfig()
        self._metrics = {"defined": 0, "milestones": 0, "tasks": 0, "results": 0,
                         "completed": 0, "abandoned": 0}

    # ------------------------------------------------------------------ #
    def define_goal(self, actor: str, text: str, horizon_days: int) -> dict[str, Any]:
        self._authorize_writer(actor)
        text = self._require(text, "hedef metni")
        goal = self._call(lambda: self._mgr.create_goal(text, int(horizon_days)))
        self._metrics["defined"] += 1
        self._emit(GoalMgmtEvents.GOAL_DEFINED, {"actor": actor, "goal_id": goal.id,
                                                 "horizon_days": goal.horizon_days})
        return goal.to_dict()

    def add_milestone(self, actor: str, goal_id: str, title: str, target_day_offset: int) -> dict[str, Any]:
        self._authorize_writer(actor)
        title = self._require(title, "milestone başlığı")
        m = self._call(lambda: self._mgr.add_milestone(goal_id, title, int(target_day_offset)))
        self._metrics["milestones"] += 1
        self._emit(GoalMgmtEvents.MILESTONE_ADDED, {"actor": actor, "goal_id": goal_id, "milestone_id": m.id})
        return m.to_dict()

    def add_task(self, actor: str, goal_id: str, milestone_id: str, description: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        description = self._require(description, "görev açıklaması")
        t = self._call(lambda: self._mgr.add_task(goal_id, milestone_id, description))
        self._metrics["tasks"] += 1
        self._emit(GoalMgmtEvents.TASK_ADDED, {"actor": actor, "goal_id": goal_id, "task_id": t.id})
        return t.to_dict()

    def record_result(self, actor: str, task_id: str, status: str,
                      result_summary: Optional[dict] = None) -> dict[str, Any]:
        """Gerçek yürütme sonucunu geri yazar → deterministik ilerleme (milestone/hedef otomatik tamamlanır)."""
        self._authorize_writer(actor)
        if status not in TASK_RESULT_STATUSES:
            raise ValidationError(f"Geçersiz görev statüsü: {status} (izinli: {TASK_RESULT_STATUSES})")
        t = self._call(lambda: self._mgr.record_task_result(task_id, status, result_summary))
        self._metrics["results"] += 1
        self._emit(GoalMgmtEvents.TASK_RESULT, {"actor": actor, "task_id": task_id, "status": status})
        goal = self._store.get_goal(t.goal_id)
        if goal is not None and goal.status == "completed":
            self._metrics["completed"] += 1
            self._emit(GoalMgmtEvents.GOAL_COMPLETED, {"goal_id": goal.id})
        return t.to_dict()

    def abandon(self, actor: str, goal_id: str, *, reason: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        goal = self._call(lambda: self._mgr.abandon_goal(goal_id))
        self._metrics["abandoned"] += 1
        self._emit(GoalMgmtEvents.GOAL_ABANDONED, {"actor": actor, "goal_id": goal_id, "reason": reason})
        return goal.to_dict()

    # ------------------------------------------------------------------ #
    def tree(self, actor: str, goal_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._call(lambda: self._mgr.goal_tree(goal_id))

    def progress(self, actor: str, goal_id: str) -> dict[str, Any]:
        self._authorize(actor)
        if self._store.get_goal(goal_id) is None:
            raise NotFoundError(f"Hedef bulunamadı: {goal_id}")
        return {"goal_id": goal_id, "progress": self._mgr.progress(goal_id)}

    def list_goals(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in ("active", "completed", "abandoned"):
            raise ValidationError(f"Geçersiz hedef durumu: {status}")
        return [g.to_dict() for g in self._store.list_goals(status)]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        goals = self._store.list_goals()
        by_status = {"active": 0, "completed": 0, "abandoned": 0}
        for g in goals:
            by_status[g.status] = by_status.get(g.status, 0) + 1
        return {"total": len(goals), **{f"goals_{k}": v for k, v in by_status.items()},
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return goal_management_contract()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _call(fn):
        """E2 çekirdeğinin ValueError'larını domain hata hiyerarşisine çevirir."""
        try:
            return fn()
        except ValueError as exc:
            msg = str(exc)
            if "bulunamadı" in msg:
                raise NotFoundError(msg) from exc
            raise ValidationError(msg) from exc

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' hedef erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' hedef yazma için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
