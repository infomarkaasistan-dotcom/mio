"""MIO Core · Audit & Compliance Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Değişmez audit ledger + Constitution Compliance kaydı. Genel uyum seviyesi deterministik olarak 'en kötü'
kayıtla belirlenir (§10). Compliance yazımı admin + denetlenir. Security RBAC-audit'ini tamamlar (ayrı kapsam).
authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, AuditEvents, audit_contract
from .models import (
    AuditConfig,
    AuditRecord,
    ComplianceLevel,
    ComplianceRecord,
    Severity,
    UnauthorizedError,
    ValidationError,
)
from .repository import AuditRepository

logger = logging.getLogger("mio.domain.audit")

_VALID_OUTCOMES = {"success", "failure", "blocked", "denied"}


class AuditComplianceDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: AuditRepository, *, bus=None,
                 config: Optional[AuditConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or AuditConfig()
        self._metrics = {"logged": 0, "assessments": 0, "exceptions": 0}

    # ------------------------------------------------------------------ #
    def log(self, actor: str, action: str, *, resource: str = "", outcome: str = "success",
            severity: str = Severity.INFO, detail: str = "") -> dict[str, Any]:
        """Kritik bir platform işlemini DEĞİŞMEZ ledger'a yazar (append-only)."""
        if not self._cfg.can_write_audit(actor):
            raise UnauthorizedError(f"'{actor}' audit yazımı için yetkili değil")
        action = self._require(action, "eylem (action)")
        if outcome not in _VALID_OUTCOMES:
            raise ValidationError(f"Geçersiz sonuç: {outcome} (izinli: {sorted(_VALID_OUTCOMES)})")
        rec = AuditRecord(actor=actor, action=action, resource=resource, outcome=outcome,
                          severity=severity, detail=detail)
        self._repo.append_audit(rec)
        self._metrics["logged"] += 1
        self._emit(AuditEvents.LOGGED, {"actor": actor, "action": action, "outcome": outcome})
        return rec.to_dict()

    def trail(self, actor: str, *, target_actor: Optional[str] = None, action: Optional[str] = None,
              outcome: Optional[str] = None, limit: Optional[int] = None) -> list[dict[str, Any]]:
        self._authorize_read(actor)
        n = min(int(limit or self._cfg.history_limit), self._cfg.history_limit)
        return self._repo.audit_recent(n, actor=target_actor, action=action, outcome=outcome)

    # ------------------------------------------------------------------ #
    def assess(self, actor: str, scope: str, article: str, level: str, *, note: str = "",
               planned_phase: str = "") -> dict[str, Any]:
        """Bir kapsam+madde için Constitution uyum değerlendirmesi kaydeder (admin)."""
        self._authorize_admin(actor)
        scope = self._require(scope, "kapsam")
        article = self._require(article, "madde")
        if level not in ComplianceLevel.ALL:
            raise ValidationError(f"Geçersiz uyum seviyesi: {level}")
        rec = ComplianceRecord(scope=scope, article=article, level=level, note=note,
                               planned_phase=planned_phase, assessed_by=actor)
        self._repo.put_compliance(rec)
        self._metrics["assessments"] += 1
        self._emit(AuditEvents.COMPLIANCE_ASSESSED, {"scope": scope, "article": article, "level": level})
        # Değerlendirmenin kendisi de denetlenir (izlenebilirlik)
        self._repo.append_audit(AuditRecord(actor=actor, action="compliance.assess",
                                            resource=rec.key(), detail=level))
        return rec.to_dict()

    def register_exception(self, actor: str, scope: str, article: str, reason: str, *,
                           planned_phase: str = "") -> dict[str, Any]:
        """Bilinçli istisna (EXCEPTION APPROVED) — gerekçe + planlanan faz zorunlu (§10)."""
        reason = self._require(reason, "gerekçe")
        out = self.assess(actor, scope, article, ComplianceLevel.EXCEPTION, note=reason,
                          planned_phase=planned_phase)
        self._metrics["exceptions"] += 1
        self._emit(AuditEvents.EXCEPTION_REGISTERED, {"scope": scope, "article": article,
                                                      "planned_phase": planned_phase})
        return out

    def compliance_report(self, actor: str) -> dict[str, Any]:
        """Güncel uyum durumu (sorgulanabilir). Genel seviye = 'en kötü' kayıt (deterministik)."""
        self._authorize_read(actor)
        records = self._repo.all_compliance()
        by_level = {lvl: 0 for lvl in ComplianceLevel.ALL}
        worst = ComplianceLevel.FULLY
        for r in records:
            lvl = r.get("level", ComplianceLevel.PARTIALLY)
            by_level[lvl] = by_level.get(lvl, 0) + 1
            if ComplianceLevel.RANK.get(lvl, 0) < ComplianceLevel.RANK[worst]:
                worst = lvl
        overall = worst if records else ComplianceLevel.PARTIALLY
        return {"overall": overall, "assessments": len(records), "by_level": by_level,
                "records": records}

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"audit_entries": self._repo.audit_count(),
                "failures": self._repo.audit_count(outcome="failure"),
                "denied": self._repo.audit_count(outcome="denied"),
                "compliance_records": self._repo.compliance_count(),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return audit_contract()

    # ------------------------------------------------------------------ #
    def _authorize_read(self, actor: str) -> None:
        if not self._cfg.can_read(actor):
            raise UnauthorizedError(f"'{actor}' audit/compliance okuma için yetkili değil")

    def _authorize_admin(self, actor: str) -> None:
        if not self._cfg.is_admin(actor):
            raise UnauthorizedError(f"'{actor}' compliance değerlendirmesi için yetkili değil (admin gerekir)")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
