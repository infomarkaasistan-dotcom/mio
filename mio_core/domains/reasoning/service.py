"""MIO Core · Reasoning Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Muhakeme = bilgi (Knowledge.apply / retrieve) + inançlar (E5 Cognitive) + muhakeme şablonlarının
DETERMİNİSTİK birleşimi. Kanıt uydurulmaz — yalnız mevcut bilgi/inançtan derlenir. Her muhakeme
denetlenebilir iz olarak kalıcılaştırılır. authorization · validation · events · observability · errors.

Inter-domain erişim public sözleşme üzerinden (Knowledge Domain'e 'Reasoning' kimliğiyle okur); çekirdeğe
(E5 Cognitive) yalnızca okuma yapar."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, ReasonEvents, reasoning_contract
from .models import (
    NotFoundError,
    ReasoningConfig,
    ReasoningKind,
    ReasoningTrace,
    UnauthorizedError,
    ValidationError,
)
from .repository import ReasoningRepository

logger = logging.getLogger("mio.domain.reasoning")


def _kw(text: str) -> set[str]:
    return {w.lower() for w in (text or "").replace("?", " ").split() if len(w) > 2}


class ReasoningDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, knowledge, repository: ReasoningRepository, *, cognitive=None, bus=None,
                 config: Optional[ReasoningConfig] = None) -> None:
        self._knowledge = knowledge           # KnowledgeDomain facade (public sözleşme)
        self._repo = repository
        self._cognitive = cognitive           # E5 CognitiveEngine (yalnız okuma), opsiyonel
        self._bus = bus
        self._cfg = config or ReasoningConfig()
        self._metrics = {"deduced": 0, "deliberated": 0, "consistency_checks": 0}

    # ------------------------------------------------------------------ #
    def deduce(self, actor: str, context_tags) -> dict[str, Any]:
        """İleri-zincirleme: bağlama uygulanabilir bilgiyi değerlendirip deterministik sonuç üretir."""
        self._authorize(actor)
        tags = sorted(set(context_tags or []))
        if not tags:
            raise ValidationError("deduce: en az bir bağlam etiketi gerekir")
        applied = self._knowledge.apply(self._cfg.reasoning_actor, tags)
        steps = [{"consider": a["name"], "recommendation": a["recommendation"],
                  "confidence": a["confidence"], "ktype": a["ktype"]} for a in applied]
        conclusion = " · ".join(a["recommendation"] for a in applied) or "Uygulanabilir bilgi bulunamadı."
        confidence = max((a["confidence"] for a in applied), default=0.0)
        trace = self._record(ReasoningKind.DEDUCE, {"context": tags}, steps, conclusion, confidence, actor)
        self._metrics["deduced"] += 1
        self._emit(ReasonEvents.DEDUCED, {"actor": actor, "context": tags, "matches": len(applied),
                                          "trace_id": trace.id})
        return {"conclusion": conclusion, "confidence": confidence, "matches": len(applied),
                "steps": steps, "trace_id": trace.id}

    def deliberate(self, actor: str, subject: str, *, context_tags=None,
                   template: Optional[str] = None) -> dict[str, Any]:
        """Şablonlu, adım adım muhakeme: her adıma yalnız MEVCUT kanıt (bilgi/inanç) deterministik eşlenir."""
        self._authorize(actor)
        subject = (subject or "").strip()
        if not subject:
            raise ValidationError("deliberate: konu (subject) boş olamaz")
        tmpl_name = template or self._cfg.default_template
        tmpl = self._find_template(tmpl_name)
        pool = self._evidence_pool(subject, set(context_tags or []))
        steps = []
        for question in tmpl["steps"]:
            qk = _kw(question)
            matched = [e for e in pool if qk & e["_kw"]]
            steps.append({"question": question,
                          "evidence": [{"source": e["source"], "ref": e["ref"], "text": e["text"]}
                                       for e in matched]})
        covered = sum(1 for s in steps if s["evidence"])
        total = len(steps) or 1
        confidence = round(covered / total, 4)
        top = max(pool, key=lambda e: e.get("_conf", 0.0), default=None) if pool else None
        conclusion = f"{subject}: {covered}/{total} muhakeme adımı kanıtla desteklendi."
        if top and top.get("_rec"):
            conclusion += f" Öne çıkan öneri: {top['_rec']}"
        trace = self._record(ReasoningKind.DELIBERATE,
                             {"subject": subject, "template": tmpl_name,
                              "context": sorted(set(context_tags or []))},
                             steps, conclusion, confidence, actor)
        self._metrics["deliberated"] += 1
        self._emit(ReasonEvents.DELIBERATED, {"actor": actor, "subject": subject, "template": tmpl_name,
                                              "coverage": confidence, "trace_id": trace.id})
        return {"subject": subject, "template": tmpl_name, "steps": steps, "coverage": confidence,
                "conclusion": conclusion, "trace_id": trace.id}

    def consistency_report(self, actor: str) -> dict[str, Any]:
        """İnanç çelişkilerini (E5) yüzeye çıkarır — tutarlılık denetimi (revizyona işaretli inançlar)."""
        self._authorize(actor)
        contradictions = []
        if self._cognitive is not None:
            for b in self._cognitive.contradictions():
                contradictions.append({"id": b.id, "subject": getattr(b, "subject", ""),
                                       "statement": b.statement,
                                       "reason": getattr(b, "revision_reason", "")})
        self._metrics["consistency_checks"] += 1
        self._emit(ReasonEvents.CONSISTENCY_CHECKED, {"actor": actor, "conflicts": len(contradictions)})
        return {"consistent": not contradictions, "conflicts": len(contradictions),
                "contradictions": contradictions}

    def explain(self, actor: str, trace_id: str) -> dict[str, Any]:
        """Kayıtlı bir muhakeme izini döner (açıklanabilirlik / iç-gözlem)."""
        self._authorize(actor)
        trace = self._repo.get(trace_id)
        if trace is None:
            raise NotFoundError(f"Muhakeme izi bulunamadı: {trace_id}")
        return trace.to_dict()

    def history(self, actor: str, *, limit: Optional[int] = None,
                kind: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in ReasoningKind.ALL:
            raise ValidationError(f"Geçersiz muhakeme türü: {kind}")
        n = min(int(limit or self._cfg.history_limit), self._cfg.history_limit)
        return [t.to_dict() for t in self._repo.recent(n, kind=kind)]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"traces": self._repo.count(),
                "deduce": self._repo.count(ReasoningKind.DEDUCE),
                "deliberate": self._repo.count(ReasoningKind.DELIBERATE),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return reasoning_contract()

    # ------------------------------------------------------------------ #
    def _evidence_pool(self, subject: str, tags: set[str]) -> list[dict[str, Any]]:
        """Konu + bağlam için MEVCUT kanıtı derler (uydurma yok): uygulanabilir bilgi + ilgili bilgi + inançlar."""
        pool: list[dict[str, Any]] = []
        for a in self._knowledge.apply(self._cfg.reasoning_actor, tags):
            text = f"{a['name']} {a['recommendation']}"
            pool.append({"source": "applied_knowledge", "ref": a["name"], "text": a["recommendation"],
                         "_kw": _kw(text), "_conf": a["confidence"], "_rec": a["recommendation"]})
        for k in self._knowledge.what_do_i_know(self._cfg.reasoning_actor, subject):
            text = f"{k['name']} {k['statement']} {' '.join(k.get('tags') or [])}"
            pool.append({"source": "knowledge", "ref": k["name"], "text": k["statement"],
                         "_kw": _kw(text), "_conf": k.get("confidence", 0.0), "_rec": ""})
        if self._cognitive is not None:
            sk = _kw(subject)
            for b in self._cognitive.beliefs():
                btext = f"{getattr(b, 'subject', '')} {b.statement}"
                if sk & _kw(btext):
                    pool.append({"source": "belief", "ref": b.id, "text": b.statement,
                                 "_kw": _kw(btext), "_conf": getattr(b, "confidence", 0.0), "_rec": ""})
        return pool

    def _find_template(self, name: str) -> dict[str, Any]:
        for t in self._knowledge.list_knowledge(self._cfg.reasoning_actor, ktype="reasoning_template"):
            if t["name"] == name:
                if not t.get("steps"):
                    raise ValidationError(f"Muhakeme şablonu adımsız: {name}")
                return t
        raise ValidationError(f"Muhakeme şablonu bulunamadı: {name}")

    def _record(self, kind: str, inputs: dict, steps: list, conclusion: str,
                confidence: float, actor: str) -> ReasoningTrace:
        trace = ReasoningTrace(kind=kind, inputs=inputs, steps=steps, conclusion=conclusion,
                               confidence=confidence, actor=actor)
        self._repo.put(trace)
        logger.info("Reasoning: %s (actor=%s, conf=%.2f, trace=%s)", kind, actor, confidence, trace.id)
        return trace

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' muhakeme için yetkili değil")

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
