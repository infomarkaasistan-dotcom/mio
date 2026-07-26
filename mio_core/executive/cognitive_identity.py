"""MIO Core · Cognitive Identity (ADR-0002 Madde 11), LLM-BAĞIMSIZ.

MIO yalnız kimliği OLAN değil, kendi BİLİŞSEL DURUMUNU da bilen bir sistemdir. Her önemli karar için
sürekli sorabilir: Bu kararı neden verdim? Hangi inanç buna sebep oldu? Hangi kanıt destekliyor? Ne kadar
eminim? Alternatiflerim nelerdi? Bu karar hedefime hizmet ediyor mu? İlkelerimle çelişiyor mu?

Bu iç-gözlem, mevcut Executive verisinden TÜRETİLİR (E1 DecisionLedger + E5 inançlar + Purpose ilkeleri) —
uydurma yok. Değerlendirilemeyen alanlar dürüstçe None/boş döner. Deterministik; LLM çağırmaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .state import ExecutiveState

__all__ = ["CognitiveReflection", "CognitiveIdentity"]

_WORD_RE = re.compile(r"\w+", re.UNICODE)
# Para-HARCAMA kökleri (çekim eklerini önekle yakalar: ödeme/ödemeyi, harca/harcamak...).
_MONEY_STEMS = ("öde", "satın", "harca", "ücret", "maliyet", "para", "payment", "spend", "abonelik", "sermaye")
# free/bedava kökleri — "ücretsiz" para-harcama DEĞİLDİR (aksi: maliyetsiz). Önek çakışması bunlarla elenir.
_FREE_STEMS = ("ücretsiz", "bedava", "maliyetsiz")
_COST_PRINCIPLE_TERMS = ("para", "maliyet", "ücretsiz", "sermaye", "harca")


def _touches_money(text_low: str) -> bool:
    """Metin bir HARCAMA/finansal yükümlülük içeriyor mu? 'ücretsiz/bedava' HARİÇ (onlar maliyet-azaltır)."""
    for w in _WORD_RE.findall(text_low):
        if any(w.startswith(f) for f in _FREE_STEMS):
            continue
        if any(w.startswith(m) for m in _MONEY_STEMS):
            return True
    return False


def _keywords(text: str, limit: int = 8) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 2][:limit]


@dataclass
class CognitiveReflection:
    decision_id: str
    kind: str
    chosen: str
    why: str                                        # rationale
    confidence: Optional[float]
    alternatives: list[str]
    evidence: list[str]
    expectation: str
    outcome: Optional[dict[str, Any]]
    prediction_error: Optional[float]
    related_beliefs: list[dict[str, str]] = field(default_factory=list)
    serves_active_goal: Optional[bool] = None
    principle_check: list[dict[str, str]] = field(default_factory=list)
    principle_conflict: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id, "kind": self.kind, "chosen": self.chosen, "why": self.why,
            "confidence": self.confidence, "alternatives": list(self.alternatives),
            "evidence": list(self.evidence), "expectation": self.expectation, "outcome": self.outcome,
            "prediction_error": self.prediction_error, "related_beliefs": list(self.related_beliefs),
            "serves_active_goal": self.serves_active_goal, "principle_check": list(self.principle_check),
            "principle_conflict": self.principle_conflict,
        }


class CognitiveIdentity:
    """Executive'in öz-bilişsel iç-gözlemi. E1 kararlarını E5 inançları + Purpose ilkeleriyle ilişkilendirir."""

    _LOW_CONFIDENCE = 0.4

    def __init__(self, state: ExecutiveState, *, cognitive=None) -> None:
        self._state = state
        self._cog = cognitive                       # E5 CognitiveEngine (opsiyonel; yoksa inanç bağı pasif)

    def introspect(self, decision_id: str) -> Optional[CognitiveReflection]:
        d = self._state.get_decision(decision_id)
        if d is None:
            return None
        text = f"{d.chosen} {d.rationale} {d.expectation}"
        principles, conflict = self._principle_check(text)
        conf = d.score.get("confidence") if isinstance(d.score, dict) else None
        return CognitiveReflection(
            decision_id=d.id, kind=d.kind, chosen=d.chosen, why=d.rationale,
            confidence=conf, alternatives=list(d.options), evidence=list(d.evidence_refs),
            expectation=d.expectation, outcome=d.outcome, prediction_error=d.prediction_error,
            related_beliefs=self._related_beliefs(text),
            serves_active_goal=self._serves_active_goal(d),
            principle_check=principles, principle_conflict=conflict,
        )

    def introspect_recent(self, n: int = 10) -> list[CognitiveReflection]:
        out = []
        for d in self._state.recent_decisions(limit=n):
            r = self.introspect(d.id)
            if r is not None:
                out.append(r)
        return out

    def flags(self, n: int = 50) -> list[CognitiveReflection]:
        """İç-gözlemde dikkat isteyen kararlar: ilke çelişkisi VEYA düşük güven."""
        flagged = []
        for r in self.introspect_recent(n):
            if r.principle_conflict or (r.confidence is not None and r.confidence < self._LOW_CONFIDENCE):
                flagged.append(r)
        return flagged

    # -- iç yardımcılar ----------------------------------------------------- #
    def _related_beliefs(self, text: str) -> list[dict[str, str]]:
        if self._cog is None:
            return []
        kws = _keywords(text)
        if not kws:
            return []
        out = []
        for b in self._cog.beliefs():
            hay = (b.subject + " " + b.statement).lower()
            if any(k in hay for k in kws):
                out.append({"id": b.id, "statement": b.statement})
        return out[:5]

    def _serves_active_goal(self, decision) -> Optional[bool]:
        active = {g.goal_id for g in self._state.active_goals()}
        if not active:
            return None
        blob = " ".join([decision.context_ref, decision.chosen, *decision.evidence_refs])
        if any(gid in blob for gid in active):
            return True
        return None                                 # belirlenemedi (dürüst — kanıt yok)

    def _principle_check(self, text: str) -> tuple[list[dict[str, str]], bool]:
        purpose = self._state.get_purpose()
        if purpose is None:
            return [], False
        low = text.lower()
        conflict = False
        checks: list[dict[str, str]] = []
        touches_money = _touches_money(low)
        for p in (purpose.core_principles + ([purpose.financial_rule] if purpose.financial_rule else [])):
            status = "not_evaluated"
            if any(t in p.lower() for t in _COST_PRINCIPLE_TERMS) and touches_money:
                status = "potential_conflict"       # finansal karar + maliyet-ilkesi → gözden geçir
                conflict = True
            checks.append({"principle": p, "status": status})
        return checks, conflict
