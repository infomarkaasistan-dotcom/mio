"""MIO Core · Extension SDK Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

**Anayasa: denetlenmemiş/aşırı-izinli üçüncü-taraf uzantı platforma SOKULAMAZ; etkinleştirme ONAY ister (Madde 24).**
Çekirdek: uzantı (extension) manifest registry (ad/sürüm/tür/istenen-izinler/imza) + **deterministik manifest &
izin-kapsamı (scope) doğrulama** (yayıncı/imza allowlist + istenen izinlerin grantable-allowlist ile uyumu) + uzantı
yaşam-döngüsü (registered→validated→enabled→disabled/rejected). Uzantı çalıştırma enjekte edilen host sandbox
adapter'a (DI) delege; yoksa DÜRÜSTÇE no_connector (uydurma sonuç YOK — Madde 8). En-az-yetki: yalnız istenen ve
izinli izinler verilir. Gerçek yürütme çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExtKind:
    TOOL = "tool"
    HOOK = "hook"
    PANEL = "panel"
    WORKFLOW = "workflow"
    CONNECTOR = "connector"
    ALL = {TOOL, HOOK, PANEL, WORKFLOW, CONNECTOR}


class ExtStatus:
    REGISTERED = "registered"   # kayıtlı, henüz doğrulanmadı
    VALIDATED = "validated"     # manifest+izin deterministik doğrulandı; etkinleştirilebilir
    ENABLED = "enabled"         # onaylı + etkin; çağrılabilir
    DISABLED = "disabled"       # devre dışı
    REJECTED = "rejected"       # denetimsiz/aşırı-izinli — terminal
    ALL = {REGISTERED, VALIDATED, ENABLED, DISABLED, REJECTED}


TRANSITIONS = {
    ExtStatus.REGISTERED: {ExtStatus.VALIDATED, ExtStatus.REJECTED},
    ExtStatus.VALIDATED: {ExtStatus.ENABLED, ExtStatus.DISABLED, ExtStatus.REJECTED},
    ExtStatus.ENABLED: {ExtStatus.DISABLED},
    ExtStatus.DISABLED: {ExtStatus.ENABLED, ExtStatus.REJECTED},
    ExtStatus.REJECTED: set(),
}


class ExtensionError(Exception):
    """Extension SDK Domain temel hatası."""


class ValidationError(ExtensionError):
    pass


class UnauthorizedError(ExtensionError):
    pass


class NotFoundError(ExtensionError):
    pass


class TransitionError(ExtensionError):
    pass


@dataclass
class Extension:
    name: str
    kind: str = ExtKind.TOOL
    version: str = "1.0.0"
    entry: str = ""                 # uzantı giriş tanımlayıcısı (host sandbox'ta çözülür)
    publisher: str = ""
    signature: str = ""
    requested_permissions: list = field(default_factory=list)
    granted_permissions: list = field(default_factory=list)
    description: str = ""
    status: str = ExtStatus.REGISTERED
    valid: bool = False
    validation_reasons: list = field(default_factory=list)
    connector: str = ""
    approved_by: str = ""
    rejected_reason: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "version": self.version,
                "entry": self.entry, "publisher": self.publisher, "signature": self.signature,
                "requested_permissions": list(self.requested_permissions),
                "granted_permissions": list(self.granted_permissions), "description": self.description,
                "status": self.status, "valid": self.valid,
                "validation_reasons": list(self.validation_reasons), "connector": self.connector,
                "approved_by": self.approved_by, "rejected_reason": self.rejected_reason,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Extension":
        return cls(name=d["name"], kind=d.get("kind", ExtKind.TOOL), version=d.get("version", "1.0.0"),
                   entry=d.get("entry", ""), publisher=d.get("publisher", ""),
                   signature=d.get("signature", ""),
                   requested_permissions=list(d.get("requested_permissions") or []),
                   granted_permissions=list(d.get("granted_permissions") or []),
                   description=d.get("description", ""), status=d.get("status", ExtStatus.REGISTERED),
                   valid=bool(d.get("valid", False)),
                   validation_reasons=list(d.get("validation_reasons") or []),
                   connector=d.get("connector", ""), approved_by=d.get("approved_by", ""),
                   rejected_reason=d.get("rejected_reason", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now())


@dataclass
class ExtensionConfig:
    trusted_publishers: set = field(default_factory=lambda: {"mio", "first-party"})
    # Verilebilir (grantable) izin kapsamı allowlist'i — istenen izin burada değilse uzantı reddedilir
    allowed_permissions: set = field(default_factory=lambda: {
        "read:knowledge", "read:metrics", "read:catalog", "ui:panel", "invoke:tool"})
    require_signature: bool = True
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Reasoning", "Planning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering"})
    # Madde 24: uzantı etkinleştirmeyi yalnız bunlar onaylayabilir
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors

    def evaluate(self, ext: "Extension") -> tuple[bool, list]:
        """DETERMİNİSTİK manifest & izin-kapsamı doğrulama. (valid, reasons)."""
        reasons: list = []
        if ext.publisher not in self.trusted_publishers:
            reasons.append("untrusted_publisher")
        if self.require_signature and not ext.signature.strip():
            reasons.append("unsigned")
        if ext.kind not in ExtKind.ALL:
            reasons.append("invalid_kind")
        for perm in ext.requested_permissions:      # en-az-yetki: her istenen izin allowlist'te olmalı
            if perm not in self.allowed_permissions:
                reasons.append(f"permission_not_allowed:{perm}")
        return (len(reasons) == 0, reasons)


__all__ = [
    "ExtKind", "ExtStatus", "TRANSITIONS", "Extension", "ExtensionConfig",
    "ExtensionError", "ValidationError", "UnauthorizedError", "NotFoundError", "TransitionError",
]
