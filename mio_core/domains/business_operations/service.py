"""MIO Core · Business & Operations Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Süreç registry + darboğaz/optimizasyon analizi + iş kuralı motoru (koşul→aksiyon). Tümü deterministik;
öneriler karar DEĞİL (Executive'e gider). authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, BizEvents, business_contract
from .models import (
    BizConfig,
    BusinessRule,
    NotFoundError,
    Process,
    ProcessStatus,
    ProcessStep,
    UnauthorizedError,
    ValidationError,
)
from .repository import BusinessRepository

logger = logging.getLogger("mio.domain.business_operations")


class BusinessOperationsDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: BusinessRepository, *, bus=None,
                 config: Optional[BizConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or BizConfig()
        self._metrics = {"processes": 0, "analyses": 0, "rules": 0, "evaluations": 0}

    # ------------------------------------------------------------------ #
    def register_process(self, actor: str, name: str, steps: list[dict]) -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "süreç adı")
        if not isinstance(steps, list) or not steps:
            raise ValidationError("steps: en az bir adım içeren liste olmalı")
        parsed = []
        for s in steps:
            if not isinstance(s, dict) or not str(s.get("name", "")).strip():
                raise ValidationError("her adımın 'name' alanı olmalı")
            step = ProcessStep.from_dict(s)
            if step.duration_hours < 0:
                raise ValidationError("duration_hours negatif olamaz")
            parsed.append(step)
        proc = Process(name=name, steps=parsed)
        self._repo.put_process(proc)
        self._metrics["processes"] += 1
        self._emit(BizEvents.PROCESS_REGISTERED, {"actor": actor, "id": proc.id, "steps": len(parsed)})
        return proc.to_dict()

    def analyze_process(self, actor: str, process_id: str) -> dict[str, Any]:
        """Deterministik süreç metrikleri: toplam süre, darboğaz, otomasyon oranı, roller."""
        self._authorize(actor)
        proc = self._require_process(process_id)
        total = round(sum(s.duration_hours for s in proc.steps), 4)
        bottleneck = None
        if proc.steps and total > 0:
            longest = max(proc.steps, key=lambda s: s.duration_hours)
            if longest.duration_hours / total >= self._cfg.bottleneck_ratio:
                bottleneck = {"step": longest.name, "duration_hours": longest.duration_hours,
                              "ratio": round(longest.duration_hours / total, 3)}
        automatable = [s.name for s in proc.steps if s.automatable]
        roles = sorted({s.role for s in proc.steps if s.role})
        self._metrics["analyses"] += 1
        self._emit(BizEvents.PROCESS_ANALYZED, {"id": process_id, "total_hours": total})
        return {"process_id": process_id, "steps": len(proc.steps), "total_hours": total,
                "bottleneck": bottleneck, "automatable_steps": automatable,
                "automatable_ratio": round(len(automatable) / len(proc.steps), 3) if proc.steps else 0.0,
                "roles": roles}

    def optimize_process(self, actor: str, process_id: str) -> dict[str, Any]:
        """Deterministik optimizasyon önerileri (otomasyon + darboğaz)."""
        self._authorize(actor)
        analysis = self.analyze_process(actor, process_id)
        recs = []
        for step in analysis["automatable_steps"]:
            recs.append(f"'{step}' adımı otomatikleştirilebilir (Madde: otomasyon-önce).")
        if analysis["bottleneck"]:
            b = analysis["bottleneck"]
            recs.append(f"Darboğaz '{b['step']}' toplam sürenin %{round(b['ratio'] * 100)}'i: "
                        f"böl/paralelleştir veya kaynağı artır.")
        return {"process_id": process_id, "recommendations": recs or ["Belirgin optimizasyon fırsatı yok."],
                "analysis": analysis}

    # -- iş kuralı motoru ------------------------------------------------- #
    def register_rule(self, actor: str, name: str, *, when: list, then: str,
                      priority: int = 50) -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "kural adı")
        if not when:
            raise ValidationError("kural 'when' koşulları gerektirir")
        then = self._require(then, "kural aksiyonu (then)")
        if self._repo.get_rule_by_name(name) is not None:
            raise ValidationError(f"Kural adı zaten var: {name}")
        rule = BusinessRule(name=name, when=list(when), then=then, priority=int(priority))
        self._repo.put_rule(rule)
        self._metrics["rules"] += 1
        self._emit(BizEvents.RULE_DEFINED, {"actor": actor, "id": rule.id, "name": name})
        return rule.to_dict()

    def evaluate(self, actor: str, context_tags: list) -> dict[str, Any]:
        """Bağlama uyan iş kurallarını deterministik değerlendirir → priority-sıralı aksiyonlar (öneri)."""
        self._authorize(actor)
        tags = set(context_tags or [])
        fired = [r for r in self._repo.all_rules() if r.matches(tags)]
        fired.sort(key=lambda r: r.priority, reverse=True)
        self._metrics["evaluations"] += 1
        self._emit(BizEvents.RULES_EVALUATED, {"context": sorted(tags), "fired": len(fired)})
        return {"context": sorted(tags), "actions": [{"rule": r.name, "action": r.then,
                                                      "priority": r.priority} for r in fired],
                "decision_authority": "Executive"}

    def list_processes(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in ProcessStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [p.to_dict() for p in self._repo.list_processes(status=status)]

    def list_rules(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [r.to_dict() for r in self._repo.all_rules()]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"processes": self._repo.process_count(), "rules": self._repo.rule_count(),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return business_contract()

    # ------------------------------------------------------------------ #
    def _require_process(self, process_id: str) -> Process:
        p = self._repo.get_process(process_id)
        if p is None:
            raise NotFoundError(f"Süreç bulunamadı: {process_id}")
        return p

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' iş/operasyon erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' iş/operasyon yazımı için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
