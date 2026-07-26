"""MIO Core · Autonomous Operations Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

**Anayasa (EN HASSAS): otonom aksiyon KARAR VERMEZ; Executive'e ÖNERİ (recommendation) üretir; uygulama Madde 24
onayıyla.** autonomy ≠ otonom karar. Çekirdek: operasyon kuralı (rule) registry (izle→değerlendir→öner) +
**deterministik tetik/koşul değerlendirme** (metrik eşiği; LLM'siz) + öneri üretimi + aksiyon durum makinesi
(requires_approval→executed/rejected/**no_connector**). **Kapalı-döngü otomasyon YALNIZ açıkça allowlisted güvenli
aksiyonlarda + closed_loop açıkken** (opt-in; varsayılan kapalı = güvenli). Aksiyon yürütme enjekte edilen action
adapter'a (DI) delege; yoksa DÜRÜSTÇE no_connector (uydurma sonuç YOK — Madde 8). İnsan/Executive gözetimi zorunlu.
Gerçek yürütme çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Deterministik eşik karşılaştırıcıları
COMPARATORS = {
    ">": lambda v, t: v > t,
    ">=": lambda v, t: v >= t,
    "<": lambda v, t: v < t,
    "<=": lambda v, t: v <= t,
    "==": lambda v, t: v == t,
    "!=": lambda v, t: v != t,
}


class Severity:
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ALL = {INFO, WARNING, CRITICAL}


class ProposalStatus:
    REQUIRES_APPROVAL = "requires_approval"   # Executive'e öneri (Madde 24) — varsayılan
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"
    NO_CONNECTOR = "no_connector"
    ALL = {REQUIRES_APPROVAL, EXECUTED, REJECTED, FAILED, NO_CONNECTOR}


class AutoOpsError(Exception):
    """Autonomous Operations Domain temel hatası."""


class ValidationError(AutoOpsError):
    pass


class UnauthorizedError(AutoOpsError):
    pass


class NotFoundError(AutoOpsError):
    pass


@dataclass
class OpsRule:
    name: str
    metric: str
    comparator: str
    threshold: float
    action: str                    # tetiklendiğinde önerilen aksiyon etiketi
    severity: str = Severity.WARNING
    enabled: bool = True
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "metric": self.metric, "comparator": self.comparator,
                "threshold": self.threshold, "action": self.action, "severity": self.severity,
                "enabled": self.enabled, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OpsRule":
        return cls(name=d["name"], metric=d["metric"], comparator=d["comparator"],
                   threshold=float(d["threshold"]), action=d["action"],
                   severity=d.get("severity", Severity.WARNING), enabled=bool(d.get("enabled", True)),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now())


@dataclass
class Proposal:
    rule_id: str
    action: str
    metric: str
    value: float
    severity: str = Severity.WARNING
    status: str = ProposalStatus.REQUIRES_APPROVAL
    auto: bool = False             # kapalı-döngü otomasyonla mı üretildi/yürütüldü
    result: dict = field(default_factory=dict)
    error: str = ""
    connector: str = ""
    approved_by: str = ""
    rejected_reason: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "rule_id": self.rule_id, "action": self.action, "metric": self.metric,
                "value": self.value, "severity": self.severity, "status": self.status, "auto": self.auto,
                "result": self.result, "error": self.error, "connector": self.connector,
                "approved_by": self.approved_by, "rejected_reason": self.rejected_reason,
                "created_at": self.created_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Proposal":
        return cls(rule_id=d["rule_id"], action=d["action"], metric=d["metric"], value=float(d["value"]),
                   severity=d.get("severity", Severity.WARNING),
                   status=d.get("status", ProposalStatus.REQUIRES_APPROVAL), auto=bool(d.get("auto", False)),
                   result=dict(d.get("result") or {}), error=d.get("error", ""),
                   connector=d.get("connector", ""), approved_by=d.get("approved_by", ""),
                   rejected_reason=d.get("rejected_reason", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), finished_at=d.get("finished_at"))


@dataclass
class AutoOpsConfig:
    # Kapalı-döngü otomasyona izinli GÜVENLİ aksiyonlar (allowlist) — yalnız bunlar auto-execute olabilir
    safe_actions: set = field(default_factory=set)
    # Kapalı-döngü otomasyon ana anahtarı (varsayılan KAPALI = güvenli; her şey öneri kalır)
    closed_loop_enabled: bool = False
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Planning", "Reasoning", "Perception"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering"})
    # Madde 24: öneriyi uygulamayı yalnız bunlar onaylayabilir
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors

    def may_auto_execute(self, action: str) -> bool:
        """Kapalı-döngü YALNIZ açıkça allowlisted güvenli aksiyonlarda + closed_loop açıkken."""
        return self.closed_loop_enabled and action in self.safe_actions


__all__ = [
    "COMPARATORS", "Severity", "ProposalStatus", "OpsRule", "Proposal", "AutoOpsConfig",
    "AutoOpsError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
