"""MIO Core · E4 — Decision & Governance (deterministik geçit, LLM-BAĞIMSIZ).

Her önemli karar bu geçitten geçer:
    HİZA (E1.consult) → SKOR (risk/güven/öncelik/bileşik) → POLICY (deterministik kurallar) →
    ONAY-KAPISI (geri-alınamaz/dış → owner) → VARDA → E1 karar defterine KAYIT (gerekçeyle).

E4 kararı ÜRETMEZ (onu E5 yaşayan zihin + E3 review üretir); E4 onu **disipline eder, mühürler,
kaydeder**. Ayrı/ikinci karar mekanizması değildir — tek Executive'in governance faseti.

LLM burada YOKTUR. Skorlama ve policy deterministiktir; LLM (danışman) yalnız dışarıdan seçenek/risk
görüşü önerebilir, ama vardayı deterministik mantık verir. LLM olmadan tam çalışır.

MarkaAsistan `decision_scoring` (risk/confidence/priority/composite) ve `policy_engine` (validate +
concurrency + approval_gate) desenlerinden UYARLANDI — kopya değil, MIO Core deyimi (stdlib, model-bağımsız,
generic DecisionRequest üzerinde). Daha zengin bir skorlayıcı/policy ileride adaptörle takılabilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Protocol

from .models import Decision, DecisionStatus
from .state import ExecutiveState, ExecutiveContext

__all__ = [
    "Verdict",
    "DecisionRequest",
    "DecisionScore",
    "PolicyViolation",
    "PolicyRule",
    "DecisionScorer",
    "DeterministicScorer",
    "GovernanceResult",
    "GovernanceEngine",
    "alignment_rule",
    "capability_rule",
    "budget_rule",
    "concurrency_rule",
]


class Verdict(str, Enum):
    APPROVE = "approve"                 # geçerli → Execution yürütebilir
    REJECT = "reject"                   # policy ihlali / capability yok / hizasız
    REVISE = "revise"                   # düzeltilebilir engel → geri gönder (defter'e YAZILMAZ)
    AWAIT_APPROVAL = "await_approval"   # geri-alınamaz/dış → owner onayı
    ESCALATE = "escalate"              # yüksek risk + düşük güven → owner'a
    DEFER = "defer"                    # yeterli kanıt yok → önce araştır (E3 Evidence Acquisition)


REVERSIBLE, IRREVERSIBLE, EXTERNAL = "reversible", "irreversible", "external"


@dataclass
class DecisionRequest:
    """Executive'in disipline edilecek sonuçlu bir seçimi (E5/E3/owner/Execution kaynağından)."""

    kind: str
    chosen: str
    options: list[str] = field(default_factory=list)
    context_ref: str = ""
    topic: str = ""                                  # consult ilgi araması için (boşsa kind+chosen)
    expectation: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    goal_id: Optional[str] = None
    required_capabilities: list[str] = field(default_factory=list)
    reversibility: str = REVERSIBLE                  # reversible | irreversible | external
    needs_evidence: bool = False                     # çağıran yeterli temel olmadığını bildirir → DEFER
    needed_evidence: list[str] = field(default_factory=list)
    source: str = "executive"

    def consult_topic(self) -> str:
        return self.topic or f"{self.kind} {self.chosen}".strip()


@dataclass
class DecisionScore:
    risk: float
    confidence: float
    priority: float
    composite: float

    def to_dict(self) -> dict[str, float]:
        return {"risk": self.risk, "confidence": self.confidence,
                "priority": self.priority, "composite": self.composite}


@dataclass
class PolicyViolation:
    rule: str
    message: str
    severity: str = "hard"                            # hard → REJECT ; soft → REVISE


# Bir policy kuralı: (request, context) -> ihlal ya da None. Takılabilir (pluggable).
PolicyRule = Callable[[DecisionRequest, ExecutiveContext], Optional[PolicyViolation]]


class DecisionScorer(Protocol):
    def score(self, request: DecisionRequest, context: ExecutiveContext) -> DecisionScore: ...


class DeterministicScorer:
    """LLM'siz, açıklanabilir skorlayıcı. Sinyaller: geri-alınabilirlik, kanıt varlığı, hedef-hizası,
    aktif strateji, ilgili dersler. Aynı girdi → aynı skor."""

    def score(self, request: DecisionRequest, context: ExecutiveContext) -> DecisionScore:
        has_evidence = bool(request.evidence_refs)
        active_goal_ids = {g.goal_id for g in context.active_goals}
        aligned = bool(request.goal_id) and request.goal_id in active_goal_ids
        has_strategy = bool(request.goal_id) and any(
            s.goal_id == request.goal_id for s in context.active_strategies)

        risk = 0.1
        if request.reversibility == IRREVERSIBLE:
            risk += 0.30
        elif request.reversibility == EXTERNAL:
            risk += 0.45
        if not has_evidence:
            risk += 0.20
        if request.goal_id and not aligned:
            risk += 0.25
        risk = min(1.0, risk)

        confidence = 0.30
        if has_evidence:
            confidence += 0.25
        if aligned:
            confidence += 0.15
        if has_strategy:
            confidence += 0.10
        if context.relevant_lessons:
            confidence += 0.05
        confidence = min(1.0, confidence)

        priority = 0.30
        if aligned:
            priority += 0.40
        if context.mission is not None:
            priority += 0.10
        priority = min(1.0, priority)

        composite = 0.4 * confidence + 0.4 * priority + 0.2 * (1.0 - risk)
        return DecisionScore(risk=round(risk, 3), confidence=round(confidence, 3),
                             priority=round(priority, 3), composite=round(composite, 3))


# --------------------------------------------------------------------------- #
# Built-in deterministik policy kuralları (takılabilir). Provider yoksa kural PASİF (dürüst — uydurmaz).
# --------------------------------------------------------------------------- #
def alignment_rule() -> PolicyRule:
    """Hedef verildiyse aktif olmalı (yetim/hizasız üretim yok — MIO Madde 9)."""
    def _rule(req: DecisionRequest, ctx: ExecutiveContext) -> Optional[PolicyViolation]:
        if req.goal_id and req.goal_id not in {g.goal_id for g in ctx.active_goals}:
            return PolicyViolation("alignment", f"Hedef aktif değil: {req.goal_id}", "hard")
        return None
    return _rule


def capability_rule(is_available: Callable[[str], bool]) -> PolicyRule:
    """Gereken yetenek BAĞLI değilse reddet (dürüstlük — sahte iş yok, Madde XX)."""
    def _rule(req: DecisionRequest, ctx: ExecutiveContext) -> Optional[PolicyViolation]:
        missing = [c for c in req.required_capabilities if not is_available(c)]
        if missing:
            return PolicyViolation("capability", f"Gereken yetenek bağlı değil: {', '.join(missing)}", "hard")
        return None
    return _rule


def budget_rule(is_exceeded: Callable[[], bool]) -> PolicyRule:
    """Kaynak/bütçe aşıldıysa düzeltme gerek (soft → REVISE)."""
    def _rule(req: DecisionRequest, ctx: ExecutiveContext) -> Optional[PolicyViolation]:
        if is_exceeded():
            return PolicyViolation("budget", "Kaynak/bütçe sınırı aşıldı", "soft")
        return None
    return _rule


def concurrency_rule(active_count: Callable[[], int], limit: int) -> PolicyRule:
    """Eşzamanlı yürütme sınırı (soft → REVISE)."""
    def _rule(req: DecisionRequest, ctx: ExecutiveContext) -> Optional[PolicyViolation]:
        if limit > 0 and active_count() >= limit:
            return PolicyViolation("concurrency", f"Eşzamanlılık sınırı ({limit}) aşıldı", "soft")
        return None
    return _rule


@dataclass
class GovernanceResult:
    verdict: Verdict
    rationale: str
    score: DecisionScore
    violations: list[PolicyViolation]
    approval_required: bool
    decision_id: Optional[str]                        # E1'e kaydedilen kararın id'si (REVISE'de None)

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict.value, "rationale": self.rationale,
                "score": self.score.to_dict(),
                "violations": [{"rule": v.rule, "message": v.message, "severity": v.severity}
                               for v in self.violations],
                "approval_required": self.approval_required, "decision_id": self.decision_id}


class GovernanceEngine:
    """E4 geçidi. E1 (ExecutiveState) ile karar defterine yazar; skorlayıcı + policy kuralları takılabilir."""

    # Deterministik varda eşikleri
    _LOW_CONFIDENCE = 0.35       # bunun altında + kanıt yok → DEFER
    _HIGH_RISK = 0.60            # sonuçlu aksiyonda bunun üstü risk → ESCALATE
    _ESCALATE_CONFIDENCE = 0.45  # sonuçlu aksiyonda bunun altı güven → ESCALATE

    def __init__(self, state: ExecutiveState, *, scorer: Optional[DecisionScorer] = None,
                 policies: Optional[list[PolicyRule]] = None,
                 is_capability_available: Optional[Callable[[str], bool]] = None,
                 is_budget_exceeded: Optional[Callable[[], bool]] = None,
                 active_execution_count: Optional[Callable[[], int]] = None,
                 concurrency_limit: int = 0) -> None:
        self._state = state
        self._scorer = scorer or DeterministicScorer()
        if policies is not None:
            self._policies = list(policies)
        else:
            self._policies = [alignment_rule()]
            if is_capability_available is not None:
                self._policies.append(capability_rule(is_capability_available))
            if is_budget_exceeded is not None:
                self._policies.append(budget_rule(is_budget_exceeded))
            if active_execution_count is not None and concurrency_limit > 0:
                self._policies.append(concurrency_rule(active_execution_count, concurrency_limit))

    def add_policy(self, rule: PolicyRule) -> None:
        self._policies.append(rule)

    def decide(self, request: DecisionRequest) -> GovernanceResult:
        context = self._state.consult(request.consult_topic())
        score = self._scorer.score(request, context)

        violations = [v for rule in self._policies if (v := rule(request, context)) is not None]
        hard = [v for v in violations if v.severity == "hard"]
        soft = [v for v in violations if v.severity == "soft"]

        # Deterministik varda sırası: REJECT > DEFER > REVISE > (sonuçlu → ESCALATE|AWAIT_APPROVAL) > APPROVE
        insufficient = request.needs_evidence or (
            score.confidence < self._LOW_CONFIDENCE and not request.evidence_refs)
        if hard:
            verdict = Verdict.REJECT
        elif insufficient:
            verdict = Verdict.DEFER
        elif soft:
            verdict = Verdict.REVISE
        elif request.reversibility in (IRREVERSIBLE, EXTERNAL):
            # Sonuçlu (geri-alınamaz/dış) aksiyon: riskli/belirsizse owner KARAR versin (ESCALATE),
            # değilse yalnız onay yeter (AWAIT_APPROVAL).
            if score.risk >= self._HIGH_RISK or score.confidence < self._ESCALATE_CONFIDENCE:
                verdict = Verdict.ESCALATE
            else:
                verdict = Verdict.AWAIT_APPROVAL
        else:
            verdict = Verdict.APPROVE

        rationale = self._rationale(verdict, score, violations)
        decision_id = self._record(request, verdict, rationale, score)
        return GovernanceResult(
            verdict=verdict, rationale=rationale, score=score, violations=violations,
            approval_required=verdict in (Verdict.AWAIT_APPROVAL, Verdict.ESCALATE),
            decision_id=decision_id,
        )

    # -- yardımcılar -------------------------------------------------------- #
    def _rationale(self, verdict: Verdict, score: DecisionScore,
                   violations: list[PolicyViolation]) -> str:
        parts = [f"[{verdict.value}] risk={score.risk} güven={score.confidence} "
                 f"öncelik={score.priority} bileşik={score.composite}"]
        if violations:
            parts.append("ihlaller: " + "; ".join(f"{v.rule}({v.severity}): {v.message}" for v in violations))
        return " | ".join(parts)

    _STATUS = {
        Verdict.APPROVE: DecisionStatus.COMMITTED,
        Verdict.DEFER: DecisionStatus.DEFERRED,
        Verdict.AWAIT_APPROVAL: DecisionStatus.AWAITING_APPROVAL,
        Verdict.ESCALATE: DecisionStatus.AWAITING_APPROVAL,
        Verdict.REJECT: DecisionStatus.REJECTED,
    }

    def _record(self, request: DecisionRequest, verdict: Verdict, rationale: str,
                score: DecisionScore) -> Optional[str]:
        """Vardayı E1 karar defterine yazar (gerekçe + beklenti + kanıt + skor). REVISE kayıtlanmaz
        (henüz karar değil; çağıran düzeltip yeniden sunar). DEFER kaydı hem tam skoru hem toplanacak
        kanıt listesini taşır → E3 Evidence Acquisition kuyruğu."""
        if verdict is Verdict.REVISE:
            return None
        score_dict: dict[str, Any] = dict(score.to_dict())
        if verdict is Verdict.DEFER and request.needed_evidence:
            score_dict["needed_evidence"] = list(request.needed_evidence)
        # DEFER kaydı orijinal 'chosen'ı KORUR (durum=DEFERRED semantiği yeter) → E3 kanıt gelince
        # aynı kararı taze kanıtla yeniden sunabilir. Yalnız REJECT işaretlenir.
        chosen = f"reddedildi: {request.chosen}" if verdict is Verdict.REJECT else request.chosen
        d = self._state.record_decision(
            request.kind, chosen, rationale=rationale, context_ref=request.context_ref,
            options=request.options, score=score_dict, expectation=request.expectation,
            evidence_refs=request.evidence_refs, status=self._STATUS[verdict])
        return d.id
