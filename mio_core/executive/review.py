"""MIO Core · E3 — Executive Review (stratejik öz-yönetim döngüsü, LLM-BAĞIMSIZ).

MIO'nun amacı görev tamamlamak değil uzun-vadeli hedefleri yönetmekse, E3 bunu canlı tutar: periyodik
ya da kritik olaylardan sonra hedefleri, stratejileri ve MIO'nun KENDİ inançlarını gözden geçirir; vardaları
E4 (governance) üzerinden E1 (state) defterine yazar.

Üç yetenek (kullanıcı direktifi):
  1. GOAL REVIEW      — hedef hâlâ anlamlı/öncelikli mi? plan devam etmeli mi? strateji revize mi?
  2. BELIEF REVISION  — "inançlarım hâlâ doğru mu? varsayımlarım geçerli mi? yeni kanıt çürütüyor mu?"
  3. EVIDENCE ACQUISITION — yeterli kanıt yoksa ÖNCE araştırma başlat (DEFER'ları besler), kanıt gelince
                            kararı taze kanıtla YENİDEN sun.

E3 ayrı/ikinci karar mercii DEĞİLDİR — tek Executive'in stratejik öz-farkındalığıdır; vardalar E4'ten geçip
E1'e kaydedilir. E3 deterministiktir ve LLM çağırmaz. İnanç kaynağı (E5) ve kanıt toplayıcı (Execution)
opsiyonel ADAPTÖRLERdir; enjekte edilmezlerse o yetenek PASİF kalır (dürüst — uydurmaz).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

from .governance import DecisionRequest, GovernanceEngine, Verdict, REVERSIBLE
from .models import DecisionStatus, GoalRef, now_iso
from .state import ExecutiveState

__all__ = [
    "ReviewTrigger",
    "ReviewVerdict",
    "GoalReviewResult",
    "BeliefReviewResult",
    "EvidenceRequest",
    "ReviewReport",
    "BeliefSource",
    "EvidenceGatherer",
    "GoalSignals",
    "ExecutiveReview",
]


class ReviewTrigger(str, Enum):
    PERIODIC = "periodic"
    GOAL_COMPLETED = "goal_completed"
    GOAL_FAILED = "goal_failed"
    PREDICTION_REFUTED = "prediction_refuted"
    CONTRADICTION = "contradiction"
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    OWNER_DIRECTIVE = "owner_directive"
    PLAN_BLOCKED = "plan_blocked"
    EVIDENCE_ARRIVED = "evidence_arrived"


class ReviewVerdict(str, Enum):
    CONTINUE = "continue"                 # değişiklik yok (defter'e yazılmaz)
    REVISE_STRATEGY = "revise_strategy"
    STOP = "stop"
    REPLAN = "replan"
    REPRIORITIZE = "reprioritize"
    ABANDON_GOAL = "abandon_goal"
    ESCALATE = "escalate"
    GATHER_EVIDENCE = "gather_evidence"   # Evidence Acquisition


# --------------------------------------------------------------------------- #
# Opsiyonel adaptörler (provider yoksa ilgili yetenek pasif — dürüst)
# --------------------------------------------------------------------------- #
class GoalSignals(Protocol):
    """Hedef değerlendirme sinyalleri (world_model/decision_scoring/prediction'dan). Bilinmeyen → None."""
    def meaningful(self, goal_id: str) -> Optional[bool]: ...
    def progress(self, goal_id: str) -> Optional[float]: ...
    def risk(self, goal_id: str) -> Optional[float]: ...


class BeliefSource(Protocol):
    """E5 (yaşayan zihin) inanç adaptörü. E3 inancı REVİZE ETMEZ; kaynağa revize edildiğini bildirir."""
    def flagged_for_revision(self) -> list[dict[str, Any]]: ...   # [{id, statement, reason}]
    def mark_revised(self, belief_id: str, note: str = "") -> None: ...


class EvidenceGatherer(Protocol):
    """Execution-tarafı kanıt toplayıcı (araştırma/araç/LLM — E3'ün deterministik kapsamı DIŞI).
    E3 yalnız İSTER; toplama burada gerçekleşir. Kanıt bulunamazsa boş liste (dürüst)."""
    def gather(self, needed_evidence: list[str], context_ref: str = "") -> list[str]: ...


# --------------------------------------------------------------------------- #
# Sonuç modelleri
# --------------------------------------------------------------------------- #
@dataclass
class GoalReviewResult:
    goal_id: str
    verdict: ReviewVerdict
    rationale: str
    decision_id: Optional[str] = None            # E4→E1 kaydı (CONTINUE'da None)
    governance_verdict: Optional[str] = None     # E4'ün vardası (DEFER/APPROVE/…)


@dataclass
class BeliefReviewResult:
    belief_id: str
    action: str                                  # revised | governed(<verdict>)
    rationale: str
    decision_id: Optional[str] = None


@dataclass
class EvidenceRequest:
    decision_id: str
    needed_evidence: list[str]
    status: str = "pending"                      # pending | fulfilled
    gathered_refs: list[str] = field(default_factory=list)
    resubmitted_decision_id: Optional[str] = None


@dataclass
class ReviewReport:
    trigger: ReviewTrigger
    goal_reviews: list[GoalReviewResult] = field(default_factory=list)
    belief_reviews: list[BeliefReviewResult] = field(default_factory=list)
    evidence_requests: list[EvidenceRequest] = field(default_factory=list)
    at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger.value, "at": self.at,
            "goal_reviews": [{"goal_id": g.goal_id, "verdict": g.verdict.value,
                              "rationale": g.rationale, "decision_id": g.decision_id,
                              "governance_verdict": g.governance_verdict} for g in self.goal_reviews],
            "belief_reviews": [{"belief_id": b.belief_id, "action": b.action,
                                "rationale": b.rationale, "decision_id": b.decision_id}
                               for b in self.belief_reviews],
            "evidence_requests": [{"decision_id": e.decision_id, "needed_evidence": e.needed_evidence,
                                   "status": e.status, "gathered_refs": e.gathered_refs,
                                   "resubmitted_decision_id": e.resubmitted_decision_id}
                                  for e in self.evidence_requests],
        }


class ExecutiveReview:
    """E3 döngüsü. E1 (state) okur, E4 (governance) üzerinden karar verir/kaydeder."""

    _HIGH_RISK = 0.70
    _LOW_PROGRESS = 0.20

    def __init__(self, state: ExecutiveState, governance: GovernanceEngine, *,
                 belief_source: Optional[BeliefSource] = None,
                 evidence_gatherer: Optional[EvidenceGatherer] = None,
                 signals: Optional[GoalSignals] = None) -> None:
        self._state = state
        self._gov = governance
        self._beliefs = belief_source
        self._evidence = evidence_gatherer
        self._signals = signals

    def run(self, trigger: ReviewTrigger = ReviewTrigger.PERIODIC) -> ReviewReport:
        return ReviewReport(
            trigger=trigger,
            goal_reviews=self._review_goals(trigger),
            belief_reviews=self._review_beliefs(),
            evidence_requests=self._acquire_evidence(),
        )

    # -- 1) Goal Review ----------------------------------------------------- #
    def _review_goals(self, trigger: ReviewTrigger) -> list[GoalReviewResult]:
        results: list[GoalReviewResult] = []
        for goal in self._state.active_goals():
            verdict, rationale = self._goal_verdict(goal)
            if verdict is ReviewVerdict.CONTINUE:
                results.append(GoalReviewResult(goal.goal_id, verdict, rationale))
                continue
            # Vardayı E4 governance'tan geçir → E1 defterine yaz (E3→E4→E1 zinciri)
            req = DecisionRequest(
                kind=f"review:{verdict.value}", chosen=f"{verdict.value} @ {goal.goal_id}",
                goal_id=goal.goal_id, reversibility=REVERSIBLE, topic=goal.goal_id,
                expectation="Stratejik review vardası uygulanacak.",
                evidence_refs=[f"review:{trigger.value}"],   # review'ın kendisi bir kanıttır
            )
            gres = self._gov.decide(req)
            # ABANDON onaylandıysa E3 state'i günceller (bu bir E1-state edimidir, Execution değil)
            if verdict is ReviewVerdict.ABANDON_GOAL and gres.verdict is Verdict.APPROVE:
                self._state.untrack_goal(goal.goal_id)
            results.append(GoalReviewResult(
                goal.goal_id, verdict, rationale,
                decision_id=gres.decision_id, governance_verdict=gres.verdict.value))
        return results

    def _goal_verdict(self, goal: GoalRef) -> tuple[ReviewVerdict, str]:
        s = self._signals
        meaningful = s.meaningful(goal.goal_id) if s else None
        progress = s.progress(goal.goal_id) if s else None
        risk = s.risk(goal.goal_id) if s else None
        strategy = self._state.get_strategy(goal.goal_id)

        if meaningful is False:
            return ReviewVerdict.ABANDON_GOAL, "Hedef artık anlamlı/gerekli değil (Madde 12: meşru vazgeçiş)."
        if risk is not None and risk >= self._HIGH_RISK:
            return ReviewVerdict.ESCALATE, f"Yüksek risk ({risk:.2f}) — owner değerlendirmeli."
        if strategy is None:
            return ReviewVerdict.REVISE_STRATEGY, "Aktif strateji yok — strateji belirlenmeli."
        if progress is not None and progress < self._LOW_PROGRESS:
            return ReviewVerdict.REVISE_STRATEGY, f"İlerleme düşük ({progress:.2f}) — strateji revize edilmeli."
        return ReviewVerdict.CONTINUE, "Hedef ve strateji tutarlı, ilerliyor."

    # -- 2) Belief Revision ------------------------------------------------- #
    def _review_beliefs(self) -> list[BeliefReviewResult]:
        if self._beliefs is None:
            return []
        results: list[BeliefReviewResult] = []
        for b in self._beliefs.flagged_for_revision():
            bid = str(b.get("id", ""))
            statement = str(b.get("statement", ""))
            reason = str(b.get("reason", ""))
            req = DecisionRequest(
                kind="belief_revision", chosen=f"revize: {statement[:60]}",
                reversibility=REVERSIBLE, topic=statement,
                expectation="Çürüten kanıt ışığında inanç güncellenecek.",
                evidence_refs=[f"belief:{bid}"] + ([reason] if reason else []),
            )
            gres = self._gov.decide(req)
            if gres.verdict is Verdict.APPROVE:
                self._beliefs.mark_revised(bid, note=reason)
                action = "revised"
            else:
                action = f"governed({gres.verdict.value})"
            results.append(BeliefReviewResult(bid, action, reason or "flagged", gres.decision_id))
        return results

    # -- 3) Evidence Acquisition (DEFER'ları besler) ------------------------ #
    def _acquire_evidence(self) -> list[EvidenceRequest]:
        requests: list[EvidenceRequest] = []
        for d in self._state.deferred_decisions():
            needed = list(d.score.get("needed_evidence") or [])
            ereq = EvidenceRequest(decision_id=d.id, needed_evidence=needed)
            if self._evidence is not None:
                refs = self._evidence.gather(needed, context_ref=d.context_ref)
                if refs:
                    # Kanıt geldi → eski DEFER'ı zincire bağla + kapat, kararı taze kanıtla YENİDEN sun
                    self._state.link_outcome(
                        d.id, outcome={"evidence_gathered": refs},
                        new_status=DecisionStatus.SUPERSEDED)
                    fresh = DecisionRequest(
                        kind=d.kind, chosen=d.chosen, context_ref=d.context_ref,
                        options=d.options, evidence_refs=refs, expectation=d.expectation,
                        reversibility=REVERSIBLE)
                    gres = self._gov.decide(fresh)
                    ereq.status = "fulfilled"
                    ereq.gathered_refs = refs
                    ereq.resubmitted_decision_id = gres.decision_id
            requests.append(ereq)
        return requests
