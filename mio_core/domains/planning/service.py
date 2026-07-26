"""MIO Core · Planning Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Plan üretir, KARARLI topolojik sıralama ile bağımlılıkları çözer ve fizibilite denetler. YÜRÜTMEZ ve
KARAR VERMEZ — onay Executive/E4'e, yürütme Execution'a aittir. Opsiyonel olarak Reasoning ile planı
gerekçelendirir, Capability kaydı ile yetenek referanslarını doğrular. authorization · validation · events ·
observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contract import CONTRACT_VERSION, PlanEvents, planning_contract
from .models import (
    InfeasiblePlanError,
    Plan,
    PlanConfig,
    PlanStatus,
    PlanStep,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import PlanRepository

logger = logging.getLogger("mio.domain.planning")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlanningDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: PlanRepository, *, capabilities=None, reasoning=None, bus=None,
                 config: Optional[PlanConfig] = None) -> None:
        self._repo = repository
        self._caps = capabilities          # CapabilityRegistry (opsiyonel) — yetenek doğrulama
        self._reasoning = reasoning        # ReasoningDomain (opsiyonel) — plan gerekçesi
        self._bus = bus
        self._cfg = config or PlanConfig()
        self._metrics = {"drafted": 0, "steps_added": 0, "sequenced": 0, "approved": 0, "abandoned": 0}

    # ------------------------------------------------------------------ #
    def draft_plan(self, actor: str, objective: str, *, goal_id: Optional[str] = None) -> dict[str, Any]:
        self._authorize_writer(actor)
        plan = Plan(objective=self._require(objective, "amaç (objective)"), goal_id=goal_id)
        self._repo.put(plan)
        self._metrics["drafted"] += 1
        self._emit(PlanEvents.DRAFTED, {"actor": actor, "plan_id": plan.id, "goal_id": goal_id})
        return plan.to_dict()

    def add_step(self, actor: str, plan_id: str, description: str, *, requires: Optional[list] = None,
                 capability: Optional[str] = None, expected: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        plan = self._mutable_plan(plan_id)
        description = self._require(description, "adım açıklaması")
        if len(plan.steps) >= self._cfg.max_steps:
            raise ValidationError(f"Plan adım sınırı aşıldı ({self._cfg.max_steps})")
        req = list(requires or [])
        known = {s.id for s in plan.steps}
        for dep in req:
            if dep not in known:
                raise ValidationError(f"Bağımlılık mevcut bir adım değil: {dep}")
        step = PlanStep(description=description, requires=req, capability=capability or None,
                        expected=expected)
        plan.steps.append(step)
        plan.status = PlanStatus.DRAFT                  # yeni adım → yeniden sıralama gerekir
        self._save(plan)
        self._metrics["steps_added"] += 1
        self._emit(PlanEvents.STEP_ADDED, {"actor": actor, "plan_id": plan_id, "step_id": step.id})
        return step.to_dict()

    def sequence(self, actor: str, plan_id: str) -> dict[str, Any]:
        """Bağımlılıkları KARARLI topolojik sıralama ile çözer. Döngü → InfeasiblePlanError."""
        self._authorize_writer(actor)
        plan = self._mutable_plan(plan_id)
        if not plan.steps:
            raise ValidationError("Boş plan sıralanamaz")
        self._check_dangling(plan)
        order_ids = self._topo_sort(plan)               # deterministik
        rank = {sid: i for i, sid in enumerate(order_ids)}
        for s in plan.steps:
            s.order = rank[s.id]
            s.status = "ordered"
        plan.steps.sort(key=lambda s: s.order)
        plan.status = PlanStatus.SEQUENCED
        self._save(plan)
        self._metrics["sequenced"] += 1
        self._emit(PlanEvents.SEQUENCED, {"actor": actor, "plan_id": plan_id, "steps": len(plan.steps)})
        return {"plan_id": plan_id, "status": plan.status,
                "ordered_steps": [s.to_dict() for s in plan.steps]}

    def assess(self, actor: str, plan_id: str) -> dict[str, Any]:
        """Fizibilite denetimi (mutasyonsuz): dangling bağımlılık, döngü, bilinmeyen yetenek, kapsam."""
        self._authorize(actor)
        plan = self._require_plan(plan_id)
        issues: list[str] = []
        # 1) dangling bağımlılık
        known = {s.id for s in plan.steps}
        for s in plan.steps:
            for dep in s.requires:
                if dep not in known:
                    issues.append(f"adım {s.id}: çözülemeyen bağımlılık {dep}")
        # 2) döngü
        ordered = []
        if not any("çözülemeyen bağımlılık" in i for i in issues):
            try:
                ordered = self._topo_sort(plan)
            except InfeasiblePlanError as exc:
                issues.append(str(exc))
        # 3) yetenek doğrulama (kayıt verildiyse)
        missing_caps = []
        if self._caps is not None:
            for s in plan.steps:
                if s.capability and self._caps.get(s.capability) is None:
                    missing_caps.append(s.capability)
                    issues.append(f"adım {s.id}: bilinmeyen yetenek '{s.capability}'")
        with_cap = sum(1 for s in plan.steps if s.capability)
        coverage = round(with_cap / len(plan.steps), 3) if plan.steps else 0.0
        report = {"plan_id": plan_id, "feasible": not issues, "issues": issues,
                  "steps": len(plan.steps), "capability_coverage": coverage,
                  "missing_capabilities": sorted(set(missing_caps)),
                  "ordered_ids": ordered}
        if self._reasoning is not None:                 # opsiyonel gerekçe (deterministik, best-effort)
            try:
                report["rationale"] = self._reasoning.deduce(
                    self._cfg_reasoning_actor(), self._plan_context(plan))
            except Exception:  # noqa: BLE001 — gerekçe zorunlu değil, fizibilite denetimini bozmamalı
                pass
        return report

    def mark_approved(self, actor: str, plan_id: str) -> dict[str, Any]:
        """Planı onaylı işaretler (yürütmeye hazır). Yetki Executive/E4'e aittir; plan fizibil olmalı."""
        self._authorize_approver(actor)
        plan = self._mutable_plan(plan_id)
        report = self.assess(actor, plan_id)
        if not report["feasible"]:
            raise ValidationError(f"Fizibil olmayan plan onaylanamaz: {report['issues']}")
        if plan.status != PlanStatus.SEQUENCED:
            raise ValidationError("Önce sequence() ile sıralanmalı")
        plan.status = PlanStatus.APPROVED
        self._save(plan)
        self._metrics["approved"] += 1
        self._emit(PlanEvents.APPROVED, {"actor": actor, "plan_id": plan_id})
        return plan.to_dict()

    def abandon(self, actor: str, plan_id: str) -> None:
        self._authorize_writer(actor)
        plan = self._require_plan(plan_id)
        plan.status = PlanStatus.ABANDONED
        self._save(plan)
        self._metrics["abandoned"] += 1
        self._emit(PlanEvents.ABANDONED, {"actor": actor, "plan_id": plan_id})

    def plan_view(self, actor: str, plan_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_plan(plan_id).to_dict()

    def list_plans(self, actor: str, *, status: Optional[str] = None,
                   goal_id: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in PlanStatus.ALL:
            raise ValidationError(f"Geçersiz plan durumu: {status}")
        return [p.to_dict() for p in self._repo.list(status=status, goal_id=goal_id)]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"total": self._repo.count(),
                "sequenced": self._repo.count(PlanStatus.SEQUENCED),
                "approved": self._repo.count(PlanStatus.APPROVED),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return planning_contract()

    # ------------------------------------------------------------------ #
    # Deterministik KARARLI topolojik sıralama (Kahn; eşitlikte ekleme sırası)
    # ------------------------------------------------------------------ #
    def _topo_sort(self, plan: Plan) -> list[str]:
        idx = {s.id: i for i, s in enumerate(plan.steps)}
        indeg = {s.id: 0 for s in plan.steps}
        adj: dict[str, list[str]] = {s.id: [] for s in plan.steps}
        for s in plan.steps:
            for dep in s.requires:
                adj[dep].append(s.id)                   # dep, s'den önce gelmeli
                indeg[s.id] += 1
        ready = sorted([sid for sid, d in indeg.items() if d == 0], key=lambda x: idx[x])
        order: list[str] = []
        while ready:
            n = ready.pop(0)
            order.append(n)
            for m in adj[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m)
            ready.sort(key=lambda x: idx[x])            # kararlılık: ekleme sırasına göre
        if len(order) != len(plan.steps):
            cyc = sorted([sid for sid in indeg if sid not in set(order)], key=lambda x: idx[x])
            raise InfeasiblePlanError(f"Bağımlılık döngüsü: {cyc}")
        return order

    def _check_dangling(self, plan: Plan) -> None:
        known = {s.id for s in plan.steps}
        for s in plan.steps:
            for dep in s.requires:
                if dep not in known:
                    raise ValidationError(f"adım {s.id}: çözülemeyen bağımlılık {dep}")

    def _plan_context(self, plan: Plan) -> set[str]:
        tags = {"planning"}
        for s in plan.steps:
            if s.capability:
                tags.add(s.capability)
        return tags

    def _cfg_reasoning_actor(self) -> str:
        return "Planning"

    # ------------------------------------------------------------------ #
    def _mutable_plan(self, plan_id: str) -> Plan:
        plan = self._require_plan(plan_id)
        if plan.status == PlanStatus.ABANDONED:
            raise ValidationError(f"Terk edilmiş plan değiştirilemez: {plan_id}")
        return plan

    def _require_plan(self, plan_id: str) -> Plan:
        plan = self._repo.get(plan_id)
        if plan is None:
            raise NotFoundError(f"Plan bulunamadı: {plan_id}")
        return plan

    def _save(self, plan: Plan) -> None:
        plan.updated_at = _now()
        self._repo.put(plan)

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' planlama erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' plan yazma için yetkili değil")

    def _authorize_approver(self, actor: str) -> None:
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' plan onaylama için yetkili değil (Executive/E4)")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
