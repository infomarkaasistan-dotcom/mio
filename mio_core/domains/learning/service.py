"""MIO Core · Learning Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Sonuçtan öğrenir (beklenen↔gerçekleşen): bilgi güvenini revize eder (Knowledge.reinforce), yanlışlanan
inancı çürütür (E5.refute) ve tekrar eden başarıdan HEURİSTİK EMERGENCE üretir (Knowledge.learn). Tüm
etkiler deterministik ve kurala dayalıdır. Innate bilgi doktrinerdir — çürütülmez/silinmez. authorization ·
validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from mio_core.domains.knowledge import KnowledgeError

from .contract import CONTRACT_VERSION, LearnEvents, learning_contract
from .models import (
    LearningConfig,
    LearningEvent,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import LearningRepository

logger = logging.getLogger("mio.domain.learning")


class LearningDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: LearningRepository, *, knowledge=None, cognitive=None, bus=None,
                 config: Optional[LearningConfig] = None) -> None:
        self._repo = repository
        self._knowledge = knowledge        # KnowledgeDomain (opsiyonel) — güven revizyonu + emergence
        self._cognitive = cognitive        # E5 CognitiveEngine (opsiyonel) — inanç çürütme
        self._bus = bus
        self._cfg = config or LearningConfig()
        self._metrics = {"outcomes": 0, "reinforcements": 0, "refutations": 0, "emergences": 0}

    # ------------------------------------------------------------------ #
    def record_outcome(self, actor: str, action: str, *, success: bool, expected: str = "",
                       actual: str = "", knowledge_id: Optional[str] = None,
                       belief_id: Optional[str] = None, tags: Optional[list] = None,
                       lesson: str = "") -> dict[str, Any]:
        """Bir eylemin sonucunu işler → deterministik bilişsel güncellemeler uygular."""
        self._authorize_writer(actor)
        action = self._require(action, "eylem (action)")
        pe = 0.0 if success else 1.0
        ev = LearningEvent(action=action, success=bool(success), expected=expected, actual=actual,
                           prediction_error=pe, knowledge_id=knowledge_id, belief_id=belief_id,
                           tags=list(tags or []), lesson=lesson.strip(), actor=actor)
        # 1) Bilgi güven revizyonu (başarı → +, başarısızlık → −)
        if knowledge_id and self._knowledge is not None:
            delta = self._cfg.reinforce_step if success else -self._cfg.penalize_step
            try:
                new_conf = self._knowledge.reinforce(self._cfg.learner_actor, knowledge_id, delta=delta)
                ev.effects.append(f"knowledge:{knowledge_id} güven={new_conf}")
                self._metrics["reinforcements"] += 1
                self._emit(LearnEvents.KNOWLEDGE_REINFORCED,
                           {"actor": actor, "id": knowledge_id, "confidence": new_conf, "success": success})
            except KnowledgeError as exc:               # innate/bulunamadı → dürüstçe atla
                ev.effects.append(f"knowledge güncellenemedi: {type(exc).__name__}")
        # 2) İnanç çürütme (yalnız başarısızlıkta, yanlışlama sinyali)
        if belief_id and not success and self._cognitive is not None:
            b = self._cognitive.refute(belief_id, f"öğrenme: '{action}' beklentiyi karşılamadı")
            if b is not None:
                ev.effects.append(f"belief:{belief_id} revizyona işaretlendi")
                self._metrics["refutations"] += 1
                self._emit(LearnEvents.BELIEF_REFUTED, {"actor": actor, "id": belief_id})
        self._repo.put(ev)
        self._metrics["outcomes"] += 1
        self._emit(LearnEvents.OUTCOME_RECORDED,
                   {"actor": actor, "action": action, "success": success, "id": ev.id})
        return ev.to_dict()

    def consolidate(self, actor: str) -> dict[str, Any]:
        """Tekrar eden başarıdan HEURİSTİK EMERGENCE: yeterince kanıtlanmış eylem-bağlamı → yeni bilgi."""
        self._authorize_writer(actor)
        if self._knowledge is None:
            return {"promoted": 0, "reason": "knowledge_domain_yok"}
        counts = self._repo.success_counts()
        existing = {k["name"] for k in self._knowledge.list_knowledge(self._cfg.learner_actor)}
        events = [e for e in self._repo.all() if e.success]
        promoted = 0
        for action in sorted(counts):
            cnt = counts[action]
            if cnt < self._cfg.emergence_min_successes:
                continue
            name = f"deneyim-{action}"[:80]
            if name in existing:
                continue
            tag = self._dominant_tag(action, events)
            if tag is None:                             # uygulanabilir kural için bağlam etiketi şart
                continue
            confidence = round(min(0.9, 0.5 + 0.1 * cnt), 4)
            self._knowledge.learn(
                self._cfg.learner_actor, ktype="decision_heuristic", name=name,
                statement=f"'{action}' tekrar eden başarı gösterdi ({cnt}×).", domain="systems_thinking",
                when=[tag], then=f"'{action}' geçmişte işe yaradı; benzer bağlamda tekrar uygula.",
                confidence=confidence, tags=["emergent", action])
            promoted += 1
            self._metrics["emergences"] += 1
            self._emit(LearnEvents.HEURISTIC_EMERGED,
                       {"actor": actor, "action": action, "when": tag, "confidence": confidence})
        logger.info("Learning: emergence %d heuristik (actor=%s)", promoted, actor)
        return {"promoted": promoted}

    def lessons(self, actor: str, *, limit: Optional[int] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        n = min(int(limit or self._cfg.history_limit), self._cfg.history_limit)
        return [e.to_dict() for e in self._repo.recent(n, with_lesson=True)]

    def history(self, actor: str, *, limit: Optional[int] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        n = min(int(limit or self._cfg.history_limit), self._cfg.history_limit)
        return [e.to_dict() for e in self._repo.recent(n)]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"total": self._repo.count(),
                "successes": self._repo.count(success=True),
                "failures": self._repo.count(success=False),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return learning_contract()

    # ------------------------------------------------------------------ #
    def _dominant_tag(self, action: str, events: list[LearningEvent]) -> Optional[str]:
        counter: dict[str, int] = {}
        for e in events:
            if e.action == action:
                for t in e.tags:
                    counter[t] = counter.get(t, 0) + 1
        if not counter:
            return None
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]   # deterministik

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' öğrenme erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' öğrenme yazma için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
