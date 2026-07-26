"""MIO Core · E1 — Persistent Executive State: servis mantığı (deterministik, LLM-BAĞIMSIZ).

MIO'nun tek doğruluk kaynağı: kimlik, misyon, uzun-vadeli hedef referansları, aktif stratejiler,
karar defteri ve dersler. Her önemli karar ÖNCE `consult()` ile bu state'e danışır; hiçbir karar
yalnız mevcut konuşma bağlamına göre verilmez.

Bu katman LLM ÇAĞIRMAZ. LLM (danışman) bir strateji/ders ÖNEREBİLİR, ama buraya ancak deterministik
Executive doğrulamasından sonra `set_strategy`/`record_lesson` ile girer. LLM erişilemezse E1 tam çalışır.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .models import (
    Decision,
    DecisionStatus,
    ExecutiveContext,
    ExecutiveStateView,
    GoalRef,
    Identity,
    Lesson,
    Mission,
    Purpose,
    Strategy,
    StrategyStatus,
    now_iso,
)
from .store import ExecutiveStateStore

__all__ = ["ExecutiveState"]

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _keywords(text: str, limit: int = 8) -> list[str]:
    """Deterministik anahtar-kelime çıkarımı (ilgi araması için). Uydurma/embedding yok."""
    return [w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 2][:limit]


class ExecutiveState:
    """Persistent Executive State servisi. Depoyu bir adaptör (ExecutiveStateStore) arkasından kullanır.

    Bu sınıf saf/deterministiktir: aynı depo durumu + aynı çağrı = aynı sonuç. Yan etki yalnız depoya
    kalıcı yazımdır. Karar VERMEZ (o E4/E5), plan yürütmez (Execution), LLM çağırmaz.
    """

    def __init__(self, store: ExecutiveStateStore, *, recent_decision_count: int = 10) -> None:
        self._store = store
        self._recent_n = recent_decision_count

    # ------------------------------------------------------------------ #
    # Kimlik / Misyon — tekil, sürekli
    # ------------------------------------------------------------------ #
    def get_identity(self) -> Optional[Identity]:
        return self._store.get_identity()

    def ensure_identity(self, name: str, nature: str = "") -> Identity:
        """Kimlik yoksa oluşturur (MIO'nun tekil, sürekli doğuşu); varsa mevcut kimliği döner."""
        existing = self._store.get_identity()
        if existing is not None:
            return existing
        identity = Identity(name=name, nature=nature)
        self._store.put_identity(identity)
        return identity

    def evolve_identity(self, *, name: Optional[str] = None, nature: Optional[str] = None) -> Identity:
        """Kimliği NADİREN, sürümleyerek günceller (soy korunur; eski sürüm ezilmez, versiyon artar).
        Governance/onay E4'ün işidir; E1 yalnız sürümlü mekanizmayı sağlar."""
        cur = self._store.get_identity()
        if cur is None:
            raise ValueError("Önce ensure_identity ile kimlik oluşturulmalı")
        updated = Identity(
            name=name if name is not None else cur.name,
            nature=nature if nature is not None else cur.nature,
            id=cur.id, born_at=cur.born_at, version=cur.version + 1,
        )
        self._store.put_identity(updated)
        return updated

    def get_mission(self) -> Optional[Mission]:
        return self._store.get_mission()

    def set_mission(self, statement: str, value_priorities: Optional[list[str]] = None,
                    rationale: str = "") -> Mission:
        """Misyonu belirler/günceller (sürümlü). İlk kez → v1; sonrası → versiyon artışı + gerekçe."""
        cur = self._store.get_mission()
        version = (cur.version + 1) if cur else 1
        mission = Mission(statement=statement, value_priorities=list(value_priorities or []),
                          rationale=rationale, version=version, updated_at=now_iso())
        self._store.put_mission(mission)
        return mission

    # ------------------------------------------------------------------ #
    # Purpose — MIO neden var (doğuştan; Executive sürekli bilir; ADR-0002)
    # ------------------------------------------------------------------ #
    def get_purpose(self) -> Optional[Purpose]:
        return self._store.get_purpose()

    def ensure_purpose(self, purpose: Purpose) -> Purpose:
        """Purpose yoksa doğuştan tohumlar (Born Capable); varsa mevcut Purpose'u döner."""
        existing = self._store.get_purpose()
        if existing is not None:
            return existing
        self._store.put_purpose(purpose)
        return purpose

    def set_purpose(self, purpose: Purpose) -> Purpose:
        """Purpose'u sürümleyerek günceller (nadir, gerekçeli — E4 onayına tabi olmalı)."""
        cur = self._store.get_purpose()
        purpose.version = (cur.version + 1) if cur else 1
        purpose.updated_at = now_iso()
        self._store.put_purpose(purpose)
        return purpose

    # ------------------------------------------------------------------ #
    # Hedef referansları (E2 sahibi; E1 aktif indeksi tutar)
    # ------------------------------------------------------------------ #
    def track_goal(self, goal_id: str, status: str = "active",
                   horizon_days: Optional[int] = None) -> GoalRef:
        ref = GoalRef(goal_id=goal_id, status=status, horizon_days=horizon_days)
        self._store.put_goal_ref(ref)
        return ref

    def untrack_goal(self, goal_id: str) -> None:
        self._store.remove_goal_ref(goal_id)

    def active_goals(self) -> list[GoalRef]:
        return self._store.list_goal_refs(status="active")

    # ------------------------------------------------------------------ #
    # Aktif stratejiler (MIO Core'a özgü 1. sınıf kavram)
    # ------------------------------------------------------------------ #
    def get_strategy(self, goal_id: str) -> Optional[Strategy]:
        return self._store.get_active_strategy(goal_id)

    def set_strategy(self, goal_id: str, approach: str, rationale: str = "") -> Strategy:
        """Bir hedefin aktif stratejisini belirler. Önceki aktif strateji 'revised' olarak arşivlenir
        (silinmez — strateji geçmişi korunur). Yeni strateji aktif olur."""
        prev = self._store.get_active_strategy(goal_id)
        if prev is not None:
            prev.status = StrategyStatus.REVISED
            self._store.put_strategy(prev)
        strat = Strategy(goal_id=goal_id, approach=approach, rationale=rationale,
                         status=StrategyStatus.ACTIVE)
        self._store.put_strategy(strat)
        return strat

    def retire_strategy(self, goal_id: str, rationale: str = "") -> Optional[Strategy]:
        prev = self._store.get_active_strategy(goal_id)
        if prev is None:
            return None
        prev.status = StrategyStatus.ABANDONED
        if rationale:
            prev.rationale = (prev.rationale + " | terk: " + rationale).strip(" |")
        self._store.put_strategy(prev)
        return prev

    # ------------------------------------------------------------------ #
    # Karar defteri — tam öğrenme zinciri
    # ------------------------------------------------------------------ #
    def record_decision(self, kind: str, chosen: str, *, rationale: str = "",
                        context_ref: str = "", options: Optional[list[str]] = None,
                        score: Optional[dict[str, Any]] = None, expectation: str = "",
                        evidence_refs: Optional[list[str]] = None,
                        status: DecisionStatus = DecisionStatus.COMMITTED) -> Decision:
        """Bir Executive kararını defter'e yazar (gerekçe + beklenti + dayanılan kanıt ile).
        status=DEFERRED ise DEFER kararı: yeterli kanıt yok, önce araştırılacak (E4 direktifi)."""
        decision = Decision(
            kind=kind, chosen=chosen, rationale=rationale, context_ref=context_ref,
            options=list(options or []), score=dict(score or {}), expectation=expectation,
            evidence_refs=list(evidence_refs or []), status=status,
        )
        self._store.append_decision(decision)
        return decision

    def defer_decision(self, kind: str, *, rationale: str, context_ref: str = "",
                       options: Optional[list[str]] = None,
                       needed_evidence: Optional[list[str]] = None) -> Decision:
        """DEFER: 'karar vermek için yeterli kanıt yok → önce araştır → Review tekrar' (E4).
        REJECT/APPROVE'dan farklıdır. `needed_evidence`, E3'ün Evidence Acquisition'ını yönlendirir
        (hangi kanıtın toplanması gerektiği) ve karar skorunda saklanır."""
        score = {"needed_evidence": list(needed_evidence)} if needed_evidence else {}
        decision = Decision(
            kind=kind, chosen="defer", rationale=rationale, context_ref=context_ref,
            options=list(options or []), status=DecisionStatus.DEFERRED, score=score,
            expectation="Yeterli kanıt toplanınca yeniden değerlendirilecek.",
        )
        self._store.append_decision(decision)
        return decision

    def link_outcome(self, decision_id: str, *, outcome: dict[str, Any],
                     prediction_error: Optional[float] = None,
                     belief_update_refs: Optional[list[str]] = None,
                     new_status: Optional[DecisionStatus] = None) -> Decision:
        """Zinciri kapatır: Decision → Outcome → Prediction Error → Belief Update. Kararın gerçek-dünya
        sonucu geldiğinde çağrılır (I7 öğrenme / E3 review besler). Karar silinmez, zincir eklenir."""
        decision = self._store.get_decision(decision_id)
        if decision is None:
            raise KeyError(f"Karar bulunamadı: {decision_id}")
        decision.outcome = dict(outcome)
        if prediction_error is not None:
            decision.prediction_error = float(prediction_error)
        if belief_update_refs:
            decision.belief_update_refs = list(
                dict.fromkeys([*decision.belief_update_refs, *belief_update_refs]))
        if new_status is not None:
            decision.status = new_status
        decision.updated_at = now_iso()
        self._store.update_decision(decision)
        return decision

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        return self._store.get_decision(decision_id)

    def recent_decisions(self, limit: Optional[int] = None) -> list[Decision]:
        return self._store.list_decisions(limit=limit or self._recent_n)

    def deferred_decisions(self, limit: int = 50) -> list[Decision]:
        """Kanıt bekleyen (DEFER) kararlar — E3'ün Evidence Acquisition kuyruğu."""
        return self._store.list_decisions(limit=limit, status=DecisionStatus.DEFERRED.value)

    # ------------------------------------------------------------------ #
    # Dersler
    # ------------------------------------------------------------------ #
    def record_lesson(self, text: str, *, source: str = "experience", confidence: float = 0.5,
                      applies_to: Optional[list[str]] = None) -> Lesson:
        lesson = Lesson(text=text, source=source, confidence=confidence,
                        applies_to=list(applies_to or []))
        self._store.append_lesson(lesson)
        return lesson

    def relevant_lessons(self, topic: str, limit: int = 10) -> list[Lesson]:
        return self._store.find_lessons(_keywords(topic), limit=limit)

    # ------------------------------------------------------------------ #
    # Okuma görünümleri
    # ------------------------------------------------------------------ #
    def consult(self, topic: str = "") -> ExecutiveContext:
        """HER önemli karar/iş ÖNCE bunu çağırır: kimlik + misyon + aktif hedefler + stratejiler +
        (konuyla) ilgili dersler + son kararlar. 'Uzun-vadeli amaca hizalı mı?' değerlendirmesini besler."""
        active_goals = self._store.list_goal_refs(status="active")
        strategies = self._store.list_strategies(status="active")
        lessons = (self._store.find_lessons(_keywords(topic))
                   if topic else self._store.list_lessons(limit=10))
        return ExecutiveContext(
            identity=self._store.get_identity(),
            mission=self._store.get_mission(),
            active_goals=active_goals,
            active_strategies=strategies,
            relevant_lessons=lessons,
            recent_decisions=self._store.list_decisions(limit=self._recent_n),
        )

    def snapshot(self) -> ExecutiveStateView:
        """E3 Review + world_model + UI'nin okuduğu tam görünüm."""
        goals = self._store.list_goal_refs()
        strategies = self._store.list_strategies(status="active")
        decisions = self._store.list_decisions(limit=self._recent_n)
        lessons = self._store.list_lessons(limit=50)
        counts = {
            "goals": len(goals),
            "active_goals": sum(1 for g in goals if g.status == "active"),
            "active_strategies": len(strategies),
            "decisions": len(self._store.list_decisions(limit=10_000)),
            "deferred_decisions": len(self.deferred_decisions(limit=10_000)),
            "lessons": len(self._store.list_lessons(limit=10_000)),
        }
        return ExecutiveStateView(
            identity=self._store.get_identity(), mission=self._store.get_mission(),
            goals=goals, strategies=strategies, recent_decisions=decisions,
            lessons=lessons, counts=counts,
        )
