"""MIO Core · Vertical Domain Brains Service (production-grade), LLM-BAĞIMSIZ, deterministik.

`VerticalBrain`: paylaşılan çekirdek — bir dikey alanda DETERMİNİSTİK tavsiye üretir (Knowledge.apply +
opsiyonel Reasoning izi) ve alan GUARDRAIL'lerini uygular. **Karar VERMEZ** (decision_authority=Executive).
`VerticalBrains`: 8 beyni tek kayıt altında toplar. Guardrail'ler Anayasa'yı deterministik uygular."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, VerticalEvents, vertical_contract, verticals_layer_contract
from .models import (
    Advice,
    GateVerdict,
    NotFoundError,
    UnauthorizedError,
    VERTICAL_SPECS,
    ValidationError,
    VerticalConfig,
    VerticalSpec,
)
from .repository import AdviceRepository

logger = logging.getLogger("mio.domain.verticals")


class VerticalBrain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, spec: VerticalSpec, knowledge, repository: AdviceRepository, *, reasoning=None,
                 bus=None, config: Optional[VerticalConfig] = None) -> None:
        self.spec = spec
        self._knowledge = knowledge
        self._repo = repository
        self._reasoning = reasoning
        self._bus = bus
        self._cfg = config or VerticalConfig()
        self._metrics = {"advised": 0, "guardrail_checks": 0, "gated": 0}

    @property
    def name(self) -> str:
        return self.spec.name

    # ------------------------------------------------------------------ #
    def advise(self, actor: str, task: str, *, context_tags: Optional[list] = None) -> dict[str, Any]:
        """Alan-spesifik DETERMİNİSTİK tavsiye. Karar VERMEZ — Executive'e gider."""
        self._authorize(actor)
        task = self._require(task, "görev/soru (task)")
        tags = set(context_tags or []) | set(self.spec.focus_tags)
        reader = self._cfg.reader_actor
        applied = self._knowledge.apply(reader, tags) if tags else []
        refs = self._knowledge.what_do_i_know(reader, task, limit=3)
        considerations = [{"source": "rule", "name": a["name"], "recommendation": a["recommendation"],
                           "confidence": a["confidence"]} for a in applied]
        considerations += [{"source": "knowledge", "name": r["name"], "statement": r["statement"]}
                           for r in refs]
        recommendation = (applied[0]["recommendation"] if applied
                          else (refs[0]["statement"] if refs
                                else f"[{self.spec.title}] alanına özgü net bir kural yok; genel ilkelerle ilerle."))
        confidence = round(max((a["confidence"] for a in applied), default=0.0), 4)
        if self._reasoning is not None and tags:
            try:
                r = self._reasoning.deduce(reader, sorted(tags))
                considerations.append({"source": "reasoning", "trace_id": r["trace_id"],
                                       "conclusion": r["conclusion"]})
            except Exception as exc:  # noqa: BLE001 — gerekçe best-effort; tavsiyeyi bozmaz
                logger.debug("Vertical %s reasoning atlandı: %s", self.name, exc)
        advice = Advice(brain=self.name, task=task, recommendation=recommendation, confidence=confidence,
                        considerations=considerations, context_tags=sorted(tags), actor=actor)
        self._repo.put(advice)
        self._metrics["advised"] += 1
        self._emit(VerticalEvents.ADVISED, {"brain": self.name, "actor": actor, "advice_id": advice.id,
                                            "confidence": confidence})
        return advice.to_dict()

    def assess_action(self, actor: str, *, context_tags: Optional[list] = None,
                      user_approved: bool = False) -> dict[str, Any]:
        """Alan GUARDRAIL'lerini deterministik uygular (ör. Finance Rule, geri-alınamaz koruma)."""
        self._authorize(actor)
        tags = set(context_tags or [])
        fired = [{"trigger": t, "verdict": v, "reason": r}
                 for (t, v, r) in self.spec.gates if t in tags]
        self._metrics["guardrail_checks"] += 1
        self._emit(VerticalEvents.GUARDRAIL_CHECKED, {"brain": self.name, "fired": len(fired)})
        deny = any(g["verdict"] == GateVerdict.DENY for g in fired)
        needs = any(g["verdict"] == GateVerdict.NEEDS_APPROVAL for g in fired)
        if deny:
            verdict, allow = GateVerdict.DENY, False
        elif needs and not user_approved:
            verdict, allow = GateVerdict.NEEDS_APPROVAL, False
        else:
            verdict, allow = GateVerdict.ALLOW, True
        if fired and verdict != GateVerdict.ALLOW or (needs and user_approved):
            self._metrics["gated"] += 1
            self._emit(VerticalEvents.GUARDRAIL_GATED, {"brain": self.name, "verdict": verdict})
        return {"brain": self.name, "allow": allow, "verdict": verdict, "gates": fired,
                "user_approved": user_approved, "decision_authority": "Executive"}

    def history(self, actor: str, *, limit: Optional[int] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        n = min(int(limit or self._cfg.history_limit), self._cfg.history_limit)
        return [a.to_dict() for a in self._repo.recent(self.name, n)]

    def explain(self, actor: str, advice_id: str) -> dict[str, Any]:
        self._authorize(actor)
        a = self._repo.get(advice_id)
        if a is None or a.brain != self.name:
            raise NotFoundError(f"Tavsiye bulunamadı: {advice_id}")
        return a.to_dict()

    def stats(self) -> dict[str, Any]:
        return {"brain": self.name, "title": self.spec.title, "domain": self.spec.primary_domain,
                "advice_count": self._repo.count(self.name), **self._metrics,
                "gates": [g[0] for g in self.spec.gates], "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return vertical_contract(self.spec.name, self.spec.title, self.spec.primary_domain)

    # ------------------------------------------------------------------ #
    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' {self.spec.title} erişimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)


class VerticalBrains:
    """8 dikey alan beynini tek kayıt altında toplar (mio.verticals)."""

    def __init__(self, knowledge, repository: AdviceRepository, *, reasoning=None, bus=None,
                 config: Optional[VerticalConfig] = None) -> None:
        self._brains: dict[str, VerticalBrain] = {
            spec.name: VerticalBrain(spec, knowledge, repository, reasoning=reasoning, bus=bus, config=config)
            for spec in VERTICAL_SPECS
        }

    def get(self, name: str) -> VerticalBrain:
        brain = self._brains.get(name)
        if brain is None:
            raise NotFoundError(f"Dikey beyin bulunamadı: {name} (mevcut: {self.names()})")
        return brain

    def names(self) -> list[str]:
        return sorted(self._brains)

    def __getattr__(self, name: str) -> VerticalBrain:      # mio.verticals.finance
        try:
            return self.__dict__["_brains"][name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __getitem__(self, name: str) -> VerticalBrain:      # mio.verticals["finance"]
        return self.get(name)

    def __iter__(self):
        return iter(self._brains.values())

    def stats(self) -> dict[str, Any]:
        return {**verticals_layer_contract(),
                "advice_total": sum(b._repo.count(b.name) for b in self._brains.values()),
                "per_brain": {n: b.stats()["advice_count"] for n, b in self._brains.items()}}

    def contract(self) -> dict[str, Any]:
        return verticals_layer_contract()


__all__ = ["VerticalBrain", "VerticalBrains"]
