"""MIO Core · Audit & Compliance Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

İki sorumluluk: (1) platform-geneli DEĞİŞMEZ (append-only) audit ledger — kim, neyi, hangi kaynağa, hangi
sonuçla; (2) Constitution Compliance kaydı — Madde 36 / Governance Extensions §10 uyum seviyelerini
SORGULANABİLİR veri olarak tutar (yalnız markdown değil). Security Domain'in RBAC-audit'ini TAMAMLAR."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ComplianceLevel:
    """Governance Extensions §10."""
    FULLY = "fully_compliant"
    SUBSTANTIALLY = "substantially_compliant"
    PARTIALLY = "partially_compliant"
    EXCEPTION = "exception_approved"
    NON_COMPLIANT = "non_compliant"
    ALL = {FULLY, SUBSTANTIALLY, PARTIALLY, EXCEPTION, NON_COMPLIANT}
    # Ağırlık (yüksek = daha iyi) — genel seviye "en kötü" ile belirlenir.
    RANK = {FULLY: 4, SUBSTANTIALLY: 3, PARTIALLY: 2, EXCEPTION: 1, NON_COMPLIANT: 0}


class Severity:
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditError(Exception):
    """Audit & Compliance Domain temel hatası."""


class ValidationError(AuditError):
    pass


class UnauthorizedError(AuditError):
    pass


class NotFoundError(AuditError):
    pass


@dataclass
class AuditRecord:
    """Değişmez audit ledger girdisi (append-only)."""
    actor: str
    action: str
    resource: str = ""
    outcome: str = "success"           # success | failure | blocked | denied
    severity: str = Severity.INFO
    detail: str = ""
    at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: uuid4().hex[:16])

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "actor": self.actor, "action": self.action, "resource": self.resource,
                "outcome": self.outcome, "severity": self.severity, "detail": self.detail, "at": self.at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AuditRecord":
        return cls(actor=d["actor"], action=d["action"], resource=d.get("resource", ""),
                   outcome=d.get("outcome", "success"), severity=d.get("severity", Severity.INFO),
                   detail=d.get("detail", ""), at=d.get("at") or _now(), id=d.get("id") or uuid4().hex[:16])


@dataclass
class ComplianceRecord:
    """Bir kapsam (domain/platform) + Constitution maddesi için uyum değerlendirmesi."""
    scope: str                         # "platform" | domain adı
    article: str                       # "Madde 28" | "§10" vb.
    level: str = ComplianceLevel.PARTIALLY
    note: str = ""
    planned_phase: str = ""            # EXCEPTION için: ne zaman kapanacak
    assessed_by: str = ""
    updated_at: str = field(default_factory=_now)

    def key(self) -> str:
        return f"{self.scope}::{self.article}"

    def to_dict(self) -> dict[str, Any]:
        return {"scope": self.scope, "article": self.article, "level": self.level, "note": self.note,
                "planned_phase": self.planned_phase, "assessed_by": self.assessed_by,
                "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ComplianceRecord":
        return cls(scope=d["scope"], article=d["article"], level=d.get("level", ComplianceLevel.PARTIALLY),
                   note=d.get("note", ""), planned_phase=d.get("planned_phase", ""),
                   assessed_by=d.get("assessed_by", ""), updated_at=d.get("updated_at") or _now())


@dataclass
class AuditConfig:
    history_limit: int = 500
    auditor_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Security", "Operations", "Compliance", "Legal"})
    # Compliance değerlendirmesi/istisna yazma yetkisi
    admin_actors: set = field(default_factory=lambda: {"owner", "Executive", "Security", "Compliance"})

    def can_read(self, actor: str) -> bool:
        return actor == "owner" or actor in self.auditor_actors

    def can_write_audit(self, actor: str) -> bool:
        # Audit LOG yazımı geniş (herhangi bir yetkili bileşen kritik işlemi kaydeder)
        return actor == "owner" or actor in (self.auditor_actors | self.admin_actors) or actor in {
            "Planning", "Knowledge", "Learning", "Memory", "Communication", "Perception", "Execution",
            "Workflow", "Engineering", "Finance", "Reasoning", "Goal", "Scheduler"}

    def is_admin(self, actor: str) -> bool:
        return actor == "owner" or actor in self.admin_actors


__all__ = [
    "ComplianceLevel", "Severity", "AuditRecord", "ComplianceRecord", "AuditConfig",
    "AuditError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
