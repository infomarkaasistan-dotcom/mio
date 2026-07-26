"""MIO Core · Executive Domain Service (production-grade facade), LLM-BAĞIMSIZ.

Stratejik karar/hedef/review/orkestrasyon domain'i. Çekirdek E1-E5'i SARAR (değiştirmez) ve production
bileşenlerini ekler: authorization · validation · event-driven akış · audit · observability (metrics+log) ·
error handling · versioned contract. Public Operation'lar `contract.OPERATIONS`.

İş kuralları: (1) yetkisiz aktör çağıramaz; (2) mission/purpose/abandon owner-only; (3) her karar E4
governance'tan geçer ve E1 defterine audit'lenir; (4) her operasyon Public Event yayınlar (Dashboard/
diğer domain'ler subscribe eder); (5) Executive dış sistemle doğrudan konuşmaz."""

from __future__ import annotations

import logging
from typing import Any, Optional

from mio_core.executive.governance import DecisionRequest, GovernanceEngine, Verdict
from mio_core.executive.models import Mission, Purpose
from mio_core.executive.review import ReviewTrigger

from .contract import CONTRACT_VERSION, ExecEvents, executive_contract
from .models import (
    DecisionCommand,
    DecisionOutcome,
    ExecutiveConfig,
    GoalOutcome,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)

logger = logging.getLogger("mio.domain.executive")


class ExecutiveDomain:
    """Executive bounded context. E1-E5 + governance + review + cognitive_identity'yi tek production
    sözleşmesi altında sunar."""

    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, *, state, goals, governance: GovernanceEngine, review,
                 cognitive_identity, bus=None, config: Optional[ExecutiveConfig] = None) -> None:
        self._state = state
        self._goals = goals
        self._gov = governance
        self._review = review
        self._cid = cognitive_identity
        self._bus = bus
        self._config = config or ExecutiveConfig()
        self._metrics = {"goals_set": 0, "goals_abandoned": 0, "decisions": 0, "reviews": 0,
                         "unauthorized": 0, "validation_errors": 0}

    # ------------------------------------------------------------------ #
    # Goal Management
    # ------------------------------------------------------------------ #
    def set_goal(self, actor: str, text: str, horizon_days: int) -> GoalOutcome:
        self._authorize(actor, "set_goal")
        text = self._require_text(text, "hedef metni")
        horizon_days = self._require_horizon(horizon_days)
        goal = self._goals.create_goal(text, horizon_days)          # E2 → E1 track
        self._metrics["goals_set"] += 1
        self._emit(ExecEvents.GOAL_SET, {"actor": actor, "goal_id": goal.id, "horizon_days": horizon_days})
        logger.info("Executive: hedef belirlendi (%s) actor=%s", goal.id, actor)
        return GoalOutcome(goal.id, goal.text, goal.horizon_days, goal.status)

    def abandon_goal(self, actor: str, goal_id: str, reason: str = "") -> GoalOutcome:
        self._authorize(actor, "abandon_goal")
        try:
            goal = self._goals.abandon_goal(goal_id)                # E2 → E1 untrack
        except ValueError as e:
            raise NotFoundError(str(e)) from e
        self._metrics["goals_abandoned"] += 1
        self._emit(ExecEvents.GOAL_ABANDONED, {"actor": actor, "goal_id": goal_id, "reason": reason})
        return GoalOutcome(goal.id, goal.text, goal.horizon_days, goal.status)

    # ------------------------------------------------------------------ #
    # Decision (E4 governance + E1 audit)
    # ------------------------------------------------------------------ #
    def decide(self, actor: str, command: DecisionCommand) -> DecisionOutcome:
        self._authorize(actor, "decide")
        self._require_text(command.kind, "karar türü")
        self._require_text(command.chosen, "seçim")
        gv = self._gov.decide(DecisionRequest(
            kind=command.kind, chosen=command.chosen, goal_id=command.goal_id,
            options=command.options, expectation=command.expectation, evidence_refs=command.evidence_refs,
            reversibility=command.reversibility, needs_evidence=command.needs_evidence,
            needed_evidence=command.needed_evidence, context_ref=command.context_ref, source=actor))
        self._metrics["decisions"] += 1
        self._emit(ExecEvents.DECISION_MADE, {"actor": actor, "kind": command.kind,
                                              "verdict": gv.verdict.value, "decision_id": gv.decision_id})
        logger.info("Executive: karar (%s) verdict=%s actor=%s", command.kind, gv.verdict.value, actor)
        return DecisionOutcome(verdict=gv.verdict.value, rationale=gv.rationale,
                               decision_id=gv.decision_id, score=gv.score.to_dict(),
                               approval_required=gv.approval_required)

    # ------------------------------------------------------------------ #
    # Review (E3 stratejik döngü)
    # ------------------------------------------------------------------ #
    def review(self, trigger: str = "periodic") -> dict[str, Any]:
        try:
            trig = ReviewTrigger(trigger)
        except ValueError as e:
            raise ValidationError(f"Bilinmeyen review tetiği: {trigger}") from e
        report = self._review.run(trig)
        self._metrics["reviews"] += 1
        self._emit(ExecEvents.REVIEW_COMPLETED, {"trigger": trigger,
                                                 "goal_reviews": len(report.goal_reviews)})
        return report.to_dict()

    # ------------------------------------------------------------------ #
    # Introspection (E5 Cognitive Identity)
    # ------------------------------------------------------------------ #
    def introspect(self, decision_id: str) -> dict[str, Any]:
        r = self._cid.introspect(decision_id)
        if r is None:
            raise NotFoundError(f"Karar bulunamadı: {decision_id}")
        return r.to_dict()

    # ------------------------------------------------------------------ #
    # Kimlik / Misyon / Purpose (owner-only)
    # ------------------------------------------------------------------ #
    def set_mission(self, actor: str, statement: str, value_priorities: Optional[list] = None) -> dict:
        self._authorize(actor, "set_mission")
        statement = self._require_text(statement, "misyon")
        m = self._state.set_mission(statement, value_priorities=value_priorities or [])
        self._emit(ExecEvents.MISSION_SET, {"version": m.version})
        return m.to_dict()

    def set_purpose(self, actor: str, purpose: Purpose) -> dict:
        self._authorize(actor, "set_purpose")
        if not purpose.primary_objective:
            raise ValidationError("primary_objective boş olamaz")
        p = self._state.set_purpose(purpose)
        self._emit(ExecEvents.PURPOSE_SET, {"version": p.version})
        return p.to_dict()

    # ------------------------------------------------------------------ #
    # Status / Observability / Contract
    # ------------------------------------------------------------------ #
    def status(self) -> dict[str, Any]:
        return self._state.snapshot().to_dict()

    def metrics(self) -> dict[str, Any]:
        return {**self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return executive_contract()

    # ------------------------------------------------------------------ #
    # İç yardımcılar (authorization / validation / event)
    # ------------------------------------------------------------------ #
    def _authorize(self, actor: str, op: str) -> None:
        if not self._config.is_authorized(actor, op):
            self._metrics["unauthorized"] += 1
            logger.warning("Executive: yetkisiz erişim actor=%s op=%s", actor, op)
            raise UnauthorizedError(f"'{actor}' '{op}' için yetkili değil")

    def _require_text(self, value: str, field_name: str) -> str:
        v = (value or "").strip()
        if not v:
            self._metrics["validation_errors"] += 1
            raise ValidationError(f"{field_name} boş olamaz")
        if len(v) > self._config.max_goal_text:
            self._metrics["validation_errors"] += 1
            raise ValidationError(f"{field_name} çok uzun (>{self._config.max_goal_text})")
        return v

    def _require_horizon(self, horizon_days: int) -> int:
        try:
            h = int(horizon_days)
        except (TypeError, ValueError) as e:
            self._metrics["validation_errors"] += 1
            raise ValidationError("horizon_days sayı olmalı") from e
        if not (self._config.min_horizon_days <= h <= self._config.max_horizon_days):
            self._metrics["validation_errors"] += 1
            raise ValidationError(
                f"horizon_days {self._config.min_horizon_days}..{self._config.max_horizon_days} aralığında olmalı")
        return h

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
