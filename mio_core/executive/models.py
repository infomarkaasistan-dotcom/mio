"""MIO Core · E1 — Persistent Executive State: alan modelleri (stdlib-only, LLM-bağımsız).

Kimlik, misyon, uzun-vadeli hedef referansları, aktif stratejiler, karar defteri ve dersler.
Karar defteri, kullanıcının istediği tam öğrenme zincirini taşır:

    Expectation → Decision → Evidence → Outcome → Prediction Error → Belief Update

Böylece MIO ileride yalnız "hangi kararı verdim?" değil; neden verdim, hangi kanıta dayandım, ne
bekledim, gerçekte ne oldu, neden yanıldım ve bundan ne öğrendim sorularını da yanıtlayabilir.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

__all__ = [
    "now_iso",
    "new_id",
    "StrategyStatus",
    "DecisionStatus",
    "Identity",
    "Mission",
    "Purpose",
    "GoalRef",
    "Strategy",
    "Decision",
    "Lesson",
    "ExecutiveContext",
    "ExecutiveStateView",
]


def now_iso() -> str:
    """UTC, ISO-8601 zaman damgası (deterministik kayıt için tek biçim)."""
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:16]


class StrategyStatus(str, Enum):
    ACTIVE = "active"
    REVISED = "revised"
    ABANDONED = "abandoned"


class DecisionStatus(str, Enum):
    """Karar defterindeki bir kaydın yaşam durumu.

    DEFERRED, kullanıcı direktifidir (E4): "yeterli kanıt yok → önce araştır → Review tekrar".
    REJECT/APPROVE'dan farklıdır; karar ertelenir, iptal edilmez.
    """

    PROPOSED = "proposed"
    COMMITTED = "committed"              # APPROVE → yürütülebilir
    DEFERRED = "deferred"               # DEFER → kanıt bekleniyor
    AWAITING_APPROVAL = "awaiting_approval"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"           # sonraki bir kararla geçersiz kılındı


# --------------------------------------------------------------------------- #
# Kimlik / Misyon — tekil ve sürekli (konuşma gelir-geçer, bunlar kalıcıdır)
# --------------------------------------------------------------------------- #
@dataclass
class Identity:
    """MIO kimdir — tekil, sürekli öz-tanım."""

    name: str
    nature: str = ""
    id: str = field(default_factory=new_id)
    born_at: str = field(default_factory=now_iso)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "nature": self.nature,
                "born_at": self.born_at, "version": self.version}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Identity":
        return cls(name=d["name"], nature=d.get("nature", ""), id=d.get("id") or new_id(),
                   born_at=d.get("born_at") or now_iso(), version=int(d.get("version", 1)))


@dataclass
class Purpose:
    """MIO NEDEN var (Mission ≠ Purpose — ADR-0002 Madde 4). Doğuştan gelir; Executive sürekli bilir.

    core_principle ve values LİSTEdir (birden çok ilke/değer). Financial rule ve learning principle
    tekil metinlerdir. Nadiren, gerekçeli, sürümlü değişir."""

    primary_objective: str
    secondary_objective: str = ""
    core_principles: list[str] = field(default_factory=list)
    financial_rule: str = ""
    learning_principle: str = ""
    values: list[str] = field(default_factory=list)
    version: int = 1
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"primary_objective": self.primary_objective,
                "secondary_objective": self.secondary_objective,
                "core_principles": list(self.core_principles), "financial_rule": self.financial_rule,
                "learning_principle": self.learning_principle, "values": list(self.values),
                "version": self.version, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Purpose":
        return cls(primary_objective=d["primary_objective"],
                   secondary_objective=d.get("secondary_objective", ""),
                   core_principles=list(d.get("core_principles") or []),
                   financial_rule=d.get("financial_rule", ""),
                   learning_principle=d.get("learning_principle", ""),
                   values=list(d.get("values") or []), version=int(d.get("version", 1)),
                   updated_at=d.get("updated_at") or now_iso())


@dataclass
class Mission:
    """Kalıcı amaç + değer öncelikleri. Nadiren, gerekçeli ve sürümlü değişir."""

    statement: str
    value_priorities: list[str] = field(default_factory=list)
    rationale: str = ""
    version: int = 1
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"statement": self.statement, "value_priorities": list(self.value_priorities),
                "rationale": self.rationale, "version": self.version, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Mission":
        return cls(statement=d["statement"], value_priorities=list(d.get("value_priorities") or []),
                   rationale=d.get("rationale", ""), version=int(d.get("version", 1)),
                   updated_at=d.get("updated_at") or now_iso())


# --------------------------------------------------------------------------- #
# Hedef referansı — E2 (goal_manager) sahibidir; E1 yalnız aktif indeks + state bağı tutar
# --------------------------------------------------------------------------- #
@dataclass
class GoalRef:
    goal_id: str
    status: str = "active"          # active | completed | abandoned
    horizon_days: Optional[int] = None
    tracked_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"goal_id": self.goal_id, "status": self.status,
                "horizon_days": self.horizon_days, "tracked_at": self.tracked_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GoalRef":
        return cls(goal_id=d["goal_id"], status=d.get("status", "active"),
                   horizon_days=d.get("horizon_days"), tracked_at=d.get("tracked_at") or now_iso())


@dataclass
class Strategy:
    """Bir hedefe dönük şu anki yaklaşım — hiçbir referans projede 1. sınıf değildi; MIO Core'a özgü."""

    goal_id: str
    approach: str
    rationale: str = ""
    id: str = field(default_factory=new_id)
    status: StrategyStatus = StrategyStatus.ACTIVE
    chosen_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "goal_id": self.goal_id, "approach": self.approach,
                "rationale": self.rationale, "status": self.status.value, "chosen_at": self.chosen_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Strategy":
        return cls(goal_id=d["goal_id"], approach=d["approach"], rationale=d.get("rationale", ""),
                   id=d.get("id") or new_id(), status=StrategyStatus(d.get("status", "active")),
                   chosen_at=d.get("chosen_at") or now_iso())


# --------------------------------------------------------------------------- #
# Karar defteri — silinmez; tam öğrenme zincirini taşır
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    """Bir Executive kararı + gerekçesi + öğrenme zinciri.

    Zincir: expectation (ne bekledim) → chosen (ne karar verdim) → evidence_refs (hangi kanıta
    dayandım) → outcome (gerçekte ne oldu) → prediction_error (ne kadar yanıldım) → belief_update_refs
    (bundan hangi inanç güncellemeleri doğdu). outcome/prediction_error/belief_update_refs karar
    anında boştur; sonuç geldiğinde `link_outcome` ile bağlanır (geriye dönük öğrenme).
    """

    kind: str                                   # start_plan | set_strategy | abandon_goal | ...
    chosen: str
    rationale: str = ""
    id: str = field(default_factory=new_id)
    context_ref: str = ""
    options: list[str] = field(default_factory=list)
    score: dict[str, Any] = field(default_factory=dict)      # {risk, confidence, priority, composite}
    decided_by: str = "executive"               # daima Executive — LLM asla karar verici değil
    status: DecisionStatus = DecisionStatus.COMMITTED
    # --- öğrenme zinciri ---
    expectation: str = ""                        # kararı verirken beklediğim sonuç
    evidence_refs: list[str] = field(default_factory=list)   # dayanılan kanıt/bilgi/trace referansları
    outcome: Optional[dict[str, Any]] = None     # gerçekleşen sonuç (sonra bağlanır)
    prediction_error: Optional[float] = None     # |beklenen - gerçekleşen| (sonra bağlanır)
    belief_update_refs: list[str] = field(default_factory=list)  # sonuçtan doğan inanç güncellemeleri
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "kind": self.kind, "chosen": self.chosen, "rationale": self.rationale,
            "context_ref": self.context_ref, "options": list(self.options), "score": dict(self.score),
            "decided_by": self.decided_by, "status": self.status.value,
            "expectation": self.expectation, "evidence_refs": list(self.evidence_refs),
            "outcome": self.outcome, "prediction_error": self.prediction_error,
            "belief_update_refs": list(self.belief_update_refs),
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Decision":
        return cls(
            kind=d["kind"], chosen=d["chosen"], rationale=d.get("rationale", ""),
            id=d.get("id") or new_id(), context_ref=d.get("context_ref", ""),
            options=list(d.get("options") or []), score=dict(d.get("score") or {}),
            decided_by=d.get("decided_by", "executive"),
            status=DecisionStatus(d.get("status", "committed")),
            expectation=d.get("expectation", ""), evidence_refs=list(d.get("evidence_refs") or []),
            outcome=d.get("outcome"), prediction_error=d.get("prediction_error"),
            belief_update_refs=list(d.get("belief_update_refs") or []),
            created_at=d.get("created_at") or now_iso(), updated_at=d.get("updated_at") or now_iso(),
        )


@dataclass
class Lesson:
    """Damıtılmış çıkarım — I7 öğrenme döngüsünün Executive'e kalıcı katkısı."""

    text: str
    source: str = "experience"                  # experience | prediction_error | reflection | owner
    confidence: float = 0.5
    applies_to: list[str] = field(default_factory=list)
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "source": self.source,
                "confidence": self.confidence, "applies_to": list(self.applies_to),
                "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Lesson":
        return cls(text=d["text"], source=d.get("source", "experience"),
                   confidence=float(d.get("confidence", 0.5)), applies_to=list(d.get("applies_to") or []),
                   id=d.get("id") or new_id(), created_at=d.get("created_at") or now_iso())


# --------------------------------------------------------------------------- #
# Okuma görünümleri (türetilmiş — hiçbir karar yalnız konuşma bağlamına göre verilmez)
# --------------------------------------------------------------------------- #
@dataclass
class ExecutiveContext:
    """`consult()` çıktısı: bir karar/işten ÖNCE danışılan Executive bağlamı."""

    identity: Optional[Identity]
    mission: Optional[Mission]
    active_goals: list[GoalRef]
    active_strategies: list[Strategy]
    relevant_lessons: list[Lesson]
    recent_decisions: list[Decision]

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict() if self.identity else None,
            "mission": self.mission.to_dict() if self.mission else None,
            "active_goals": [g.to_dict() for g in self.active_goals],
            "active_strategies": [s.to_dict() for s in self.active_strategies],
            "relevant_lessons": [ls.to_dict() for ls in self.relevant_lessons],
            "recent_decisions": [d.to_dict() for d in self.recent_decisions],
        }


@dataclass
class ExecutiveStateView:
    """`snapshot()` çıktısı: E3 Review + world_model + UI'nin okuduğu tam görünüm."""

    identity: Optional[Identity]
    mission: Optional[Mission]
    goals: list[GoalRef]
    strategies: list[Strategy]
    recent_decisions: list[Decision]
    lessons: list[Lesson]
    counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict() if self.identity else None,
            "mission": self.mission.to_dict() if self.mission else None,
            "goals": [g.to_dict() for g in self.goals],
            "strategies": [s.to_dict() for s in self.strategies],
            "recent_decisions": [d.to_dict() for d in self.recent_decisions],
            "lessons": [ls.to_dict() for ls in self.lessons],
            "counts": dict(self.counts),
        }
