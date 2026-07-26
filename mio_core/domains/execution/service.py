"""MIO Core · Execution Domain Service (production-grade), LLM-BAĞIMSIZ çekirdek.

Onaylı karar/planı GERÇEK araçlarla (Tool Orchestrator) yürütür. Anayasa: **Execution ASLA tek başına karar
VERMEZ** — her yürütme bir yetkilendirmeye (onaylı plan/karar referansı) bağlıdır. `run_plan` yalnız APPROVED
planı çalıştırır; workflow fail-fast'tir ve her adım denetime yazılır. İsteğe bağlı olarak her adım sonucu
Learning'e beslenir (Plan→Execute→Learn döngüsü). authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from mio_core.execution.orchestrator import ToolRequest

from .contract import CONTRACT_VERSION, ExecEvents, execution_contract
from .models import (
    ExecutionConfig,
    ExecutionRun,
    NotFoundError,
    RunKind,
    RunStatus,
    UnauthorizedError,
    UnauthorizedExecutionError,
    ValidationError,
)
from .repository import ExecutionRepository

logger = logging.getLogger("mio.domain.execution")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, orchestrator, repository: ExecutionRepository, *, planning=None, learning=None,
                 bus=None, config: Optional[ExecutionConfig] = None) -> None:
        self._orch = orchestrator
        self._repo = repository
        self._planning = planning        # PlanningDomain (opsiyonel) — onaylı plan doğrulama
        self._learning = learning        # LearningDomain (opsiyonel) — sonuç geri-beslemesi
        self._bus = bus
        self._cfg = config or ExecutionConfig()
        self._metrics = {"capability_runs": 0, "plan_runs": 0, "steps": 0, "blocked": 0, "failed": 0}

    # ------------------------------------------------------------------ #
    def run_capability(self, actor: str, capability: str, action: str, params: Optional[dict] = None, *,
                       authorization: str = "", reversibility: str = "reversible",
                       user_approved: bool = False, goal_id: Optional[str] = None) -> dict[str, Any]:
        """Tek bir yeteneği yürütür. Yetkilendirme (onaylı plan/karar ref) zorunludur."""
        self._authorize_writer(actor)
        capability = self._require(capability, "yetenek")
        action = self._require(action, "aksiyon")
        self._require_authorization(authorization)
        res = self._orch.execute(ToolRequest(
            capability, action, dict(params or {}), requester=actor, reversibility=reversibility,
            user_approved=user_approved, goal_id=goal_id, context_ref=authorization))
        status = self._status_of(res)
        run = ExecutionRun(kind=RunKind.STEP, actor=actor, authorization=authorization, status=status,
                           steps=[self._step_dict(None, res)], finished_at=_now())
        self._repo.put(run)
        self._metrics["capability_runs"] += 1
        self._account(res)
        self._emit(ExecEvents.CAPABILITY_RUN, {"actor": actor, "capability": capability,
                                               "success": res.success, "run_id": run.id})
        if res.blocked:
            self._emit(ExecEvents.BLOCKED, {"capability": capability, "reason": res.reason})
        return {"run_id": run.id, "status": status, "success": res.success, "blocked": res.blocked,
                "output": res.output, "error": res.error, "verdict": res.verdict}

    def run_plan(self, actor: str, plan_id: str) -> dict[str, Any]:
        """Onaylı bir planın sıralı adımlarını workflow olarak yürütür (fail-fast). Onay = yetkilendirme."""
        self._authorize_writer(actor)
        if self._planning is None:
            raise ValidationError("Planning bağlı değil — plan yürütülemez")
        plan = self._fetch_plan(actor, plan_id)
        if plan.get("status") != "approved":
            raise UnauthorizedExecutionError(
                f"Yalnız APPROVED plan yürütülür (durum: {plan.get('status')}). Execution tek başına karar vermez.")
        run = ExecutionRun(kind=RunKind.PLAN, actor=actor, authorization=plan_id, plan_id=plan_id,
                           status=RunStatus.COMPLETED)
        self._metrics["plan_runs"] += 1
        self._emit(ExecEvents.PLAN_RUN_STARTED, {"actor": actor, "plan_id": plan_id, "run_id": run.id})
        for step in plan.get("steps", []):
            cap = step.get("capability")
            if not cap:                                  # yeteneksiz adım = manuel/dışsal → atlanır (dürüst)
                run.steps.append({"step_id": step.get("id"), "skipped": True,
                                  "reason": "yetenek yok (manuel adım)"})
                continue
            res = self._orch.execute(ToolRequest(
                cap, self._cfg.default_action,
                {"description": step.get("description", ""), "expected": step.get("expected", "")},
                requester=actor, goal_id=plan.get("goal_id"), context_ref=plan_id))
            sd = self._step_dict(step.get("id"), res)
            run.steps.append(sd)
            self._metrics["steps"] += 1
            self._account(res)
            self._emit(ExecEvents.STEP_EXECUTED, {"plan_id": plan_id, "step_id": step.get("id"),
                                                  "success": res.success})
            self._feed_learning(actor, step.get("description", cap), res.success, cap)
            if not res.success:                          # fail-fast
                run.status = RunStatus.BLOCKED if res.blocked else RunStatus.FAILED
                break
        run.finished_at = _now()
        self._repo.put(run)
        self._emit(ExecEvents.PLAN_RUN_FINISHED, {"plan_id": plan_id, "run_id": run.id,
                                                  "status": run.status})
        return run.to_dict()

    def history(self, actor: str, *, limit: Optional[int] = None,
                kind: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in RunKind.ALL:
            raise ValidationError(f"Geçersiz koşu türü: {kind}")
        n = min(int(limit or self._cfg.history_limit), self._cfg.history_limit)
        return [r.to_dict() for r in self._repo.recent(n, kind=kind)]

    def explain(self, actor: str, run_id: str) -> dict[str, Any]:
        self._authorize(actor)
        run = self._repo.get(run_id)
        if run is None:
            raise NotFoundError(f"Yürütme koşusu bulunamadı: {run_id}")
        return run.to_dict()

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"runs": self._repo.count(),
                "completed": self._repo.count(status=RunStatus.COMPLETED),
                "failed": self._repo.count(status=RunStatus.FAILED),
                "blocked_runs": self._repo.count(status=RunStatus.BLOCKED),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return execution_contract()

    # ------------------------------------------------------------------ #
    def _fetch_plan(self, actor: str, plan_id: str) -> dict[str, Any]:
        try:
            return self._planning.plan_view(actor, plan_id)
        except Exception as exc:  # noqa: BLE001 — planning hatasını domain hatasına çevir
            raise NotFoundError(f"Plan alınamadı: {plan_id} ({exc})") from exc

    def _feed_learning(self, actor: str, action: str, success: bool, capability: str) -> None:
        if self._learning is None:
            return
        try:
            self._learning.record_outcome(actor, action, success=success, tags=[capability])
        except Exception as exc:  # noqa: BLE001 — geri-besleme best-effort; yürütmeyi bozmaz
            logger.debug("Execution→Learning geri-besleme atlandı: %s", exc)

    @staticmethod
    def _status_of(res) -> str:
        if res.success:
            return RunStatus.COMPLETED
        return RunStatus.BLOCKED if res.blocked else RunStatus.FAILED

    @staticmethod
    def _step_dict(step_id, res) -> dict[str, Any]:
        return {"step_id": step_id, "capability": res.capability, "action": res.action,
                "success": res.success, "blocked": res.blocked, "verdict": res.verdict,
                "output": res.output, "error": res.error, "latency_ms": res.latency_ms}

    def _account(self, res) -> None:
        if res.blocked:
            self._metrics["blocked"] += 1
        elif not res.success:
            self._metrics["failed"] += 1

    def _require_authorization(self, authorization: str) -> None:
        if self._cfg.require_authorization and not (authorization or "").strip():
            raise UnauthorizedExecutionError(
                "Yürütme yetkilendirme gerektirir (onaylı plan/karar referansı). Execution tek başına karar vermez.")

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' yürütme erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' yürütme başlatma için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
