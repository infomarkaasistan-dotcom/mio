"""MIO Core · Executive Domain — modeller, hatalar, config (production-grade).

Executive Domain = stratejik karar/planlama/koordinasyon/delegasyon/hedef yönetimi/orkestrasyon bounded
context'i. Çekirdek E1-E5'i SARAR (değiştirmez). Bu dosya: domain exception'ları + API request/response
sözleşme modelleri + domain config."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Hata yönetimi (domain exception hiyerarşisi)
# --------------------------------------------------------------------------- #
class ExecutiveError(Exception):
    """Executive Domain temel hatası."""


class ValidationError(ExecutiveError):
    """Geçersiz girdi (iş kuralı ihlali)."""


class UnauthorizedError(ExecutiveError):
    """Yetkisiz aktör bir domain operasyonunu çağırdı."""


class NotFoundError(ExecutiveError):
    """İstenen kaynak (karar/hedef) yok."""


# --------------------------------------------------------------------------- #
# API / Contract modelleri (Public — Bounded Context §4)
# --------------------------------------------------------------------------- #
@dataclass
class DecisionCommand:
    kind: str
    chosen: str
    goal_id: Optional[str] = None
    options: list[str] = field(default_factory=list)
    expectation: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    reversibility: str = "reversible"          # reversible | irreversible | external
    needs_evidence: bool = False
    needed_evidence: list[str] = field(default_factory=list)
    context_ref: str = ""


@dataclass
class DecisionOutcome:
    verdict: str                               # approve/reject/revise/defer/await_approval/escalate
    rationale: str
    decision_id: Optional[str]
    score: dict[str, Any]
    approval_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "rationale": self.rationale, "decision_id": self.decision_id,
                "score": self.score, "approval_required": self.approval_required}


@dataclass
class GoalOutcome:
    goal_id: str
    text: str
    horizon_days: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"goal_id": self.goal_id, "text": self.text, "horizon_days": self.horizon_days,
                "status": self.status}


# --------------------------------------------------------------------------- #
# Configuration yönetimi
# --------------------------------------------------------------------------- #
_DEFAULT_ACTORS = {
    "owner", "Executive", "Business", "Finance", "Marketing", "Sales", "Product", "Engineering",
    "Knowledge", "Security", "Operations", "Workflow", "Learning", "Communication", "Identity",
}


@dataclass
class ExecutiveConfig:
    owner: str = "owner"
    authorized_actors: set = field(default_factory=lambda: set(_DEFAULT_ACTORS))
    owner_only_ops: set = field(default_factory=lambda: {"set_mission", "set_purpose", "abandon_goal"})
    max_goal_text: int = 500
    min_horizon_days: int = 1
    max_horizon_days: int = 730

    def is_authorized(self, actor: str, op: str) -> bool:
        if op in self.owner_only_ops:
            return actor == self.owner
        return actor == self.owner or actor in self.authorized_actors
