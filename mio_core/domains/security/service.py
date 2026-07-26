"""MIO Core · Security Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Merkezî RBAC yetki kararı + append-only güvenlik denetimi + secret redaksiyonu + kilitleme. Yetki kararı
deterministiktir (rol izinleri ∪ doğrudan grant'ler). Ardışık başarısız kontrol eşiği aşınca principal
kilitlenir. Tüm denetim detayları YAZILMADAN ÖNCE redakte edilir (Anayasa: secret asla loglanmaz).
authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contract import CONTRACT_VERSION, SecEvents, security_contract
from .models import (
    NotFoundError,
    Permission,
    Principal,
    Role,
    SecurityAudit,
    SecurityConfig,
    Severity,
    UnauthorizedError,
    ValidationError,
    default_principals,
    redact,
)
from .repository import SecurityRepository

logger = logging.getLogger("mio.domain.security")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SecurityDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: SecurityRepository, *, bus=None,
                 config: Optional[SecurityConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or SecurityConfig()
        self._metrics = {"checks": 0, "denials": 0, "locks": 0, "events": 0}
        if self._repo.principal_count() == 0:           # doğuştan kimlikler/roller
            for p in default_principals():
                self._repo.put_principal(p)

    # ------------------------------------------------------------------ #
    def check(self, principal: str, permission: str, *, resource: str = "") -> dict[str, Any]:
        """Deterministik RBAC yetki kararı + denetim. Ardışık başarısızlık eşiği aşınca kilitler."""
        self._metrics["checks"] += 1
        if permission not in Permission.ALL:
            raise ValidationError(f"Geçersiz izin: {permission}")
        p = self._repo.get_principal(principal)
        if p is None:
            self._deny(principal, permission, "bilinmeyen principal")
            return self._decision(principal, permission, False, "bilinmeyen principal", False)
        if p.locked:
            self._deny(principal, permission, "principal kilitli", persist=False)
            return self._decision(principal, permission, False, "kilitli", True)
        allowed = permission in p.effective_permissions()
        if allowed:
            if p.failed_checks:
                p.failed_checks = 0
                self._repo.put_principal(p)
            self._emit(SecEvents.CHECK, {"principal": principal, "permission": permission, "allowed": True})
            return self._decision(principal, permission, True, "izin verildi", False)
        # reddedildi → sayaç + olası kilit
        p.failed_checks += 1
        reason = "izin yok"
        locked = False
        if p.failed_checks >= self._cfg.lockout_threshold:
            p.locked = True
            locked = True
            self._metrics["locks"] += 1
        self._repo.put_principal(p)
        self._deny(principal, permission, reason, persist=False)
        if locked:
            self._audit(SecEvents.LOCKED, principal, "ardışık başarısız kontrol → kilit", Severity.CRITICAL)
            self._emit(SecEvents.LOCKED, {"principal": principal})
        return self._decision(principal, permission, False, reason, locked)

    def authorize(self, principal: str, permission: str) -> bool:
        return self.check(principal, permission)["allowed"]

    # -- yönetim (admin) --------------------------------------------------- #
    def register_principal(self, actor: str, name: str, *, roles: Optional[list] = None,
                           grants: Optional[list] = None) -> dict[str, Any]:
        self._authorize_admin(actor)
        name = self._require(name, "principal adı")
        rs = list(roles or [])
        gs = list(grants or [])
        self._validate_roles(rs)
        self._validate_perms(gs)
        p = Principal(name=name, roles=rs, grants=gs)
        self._repo.put_principal(p)
        self._principal_changed(actor, name, "kayıt")
        return p.to_dict()

    def grant(self, actor: str, name: str, permission: str) -> dict[str, Any]:
        self._authorize_admin(actor)
        self._validate_perms([permission])
        p = self._require_principal(name)
        if permission not in p.grants:
            p.grants.append(permission)
            self._repo.put_principal(p)
        self._principal_changed(actor, name, f"grant:{permission}")
        return p.to_dict()

    def revoke(self, actor: str, name: str, permission: str) -> dict[str, Any]:
        self._authorize_admin(actor)
        p = self._require_principal(name)
        if permission in p.grants:
            p.grants.remove(permission)
            self._repo.put_principal(p)
        self._principal_changed(actor, name, f"revoke:{permission}")
        return p.to_dict()

    def assign_role(self, actor: str, name: str, role: str) -> dict[str, Any]:
        self._authorize_admin(actor)
        self._validate_roles([role])
        p = self._require_principal(name)
        if role not in p.roles:
            p.roles.append(role)
            self._repo.put_principal(p)
        self._principal_changed(actor, name, f"role:{role}")
        return p.to_dict()

    def lock(self, actor: str, name: str) -> dict[str, Any]:
        self._authorize_admin(actor)
        p = self._require_principal(name)
        p.locked = True
        self._repo.put_principal(p)
        self._audit(SecEvents.LOCKED, name, f"{actor} tarafından kilitlendi", Severity.WARNING)
        self._emit(SecEvents.LOCKED, {"principal": name, "by": actor})
        return p.to_dict()

    def unlock(self, actor: str, name: str) -> dict[str, Any]:
        self._authorize_admin(actor)
        p = self._require_principal(name)
        p.locked = False
        p.failed_checks = 0
        self._repo.put_principal(p)
        self._audit(SecEvents.UNLOCKED, name, f"{actor} tarafından açıldı", Severity.INFO)
        self._emit(SecEvents.UNLOCKED, {"principal": name, "by": actor})
        return p.to_dict()

    # -- denetim + redaksiyon --------------------------------------------- #
    def record_event(self, actor: str, kind: str, detail: str, *, severity: str = Severity.INFO,
                     principal: str = "") -> dict[str, Any]:
        self._authorize_admin(actor)
        kind = self._require(kind, "olay türü")
        a = self._audit(kind, principal or actor, detail, severity)   # detail redakte edilir
        return a.to_dict()

    def audit_trail(self, actor: str, *, limit: Optional[int] = None,
                    principal: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize_admin(actor)
        n = min(int(limit or self._cfg.history_limit), self._cfg.history_limit)
        return self._repo.audit_recent(n, principal=principal)

    def principal(self, actor: str, name: str) -> dict[str, Any]:
        self._authorize_admin(actor)
        return self._require_principal(name).to_dict()

    @staticmethod
    def redact(text: str) -> str:
        """Secret desenlerini maskeler (Anayasa: secret asla loglanmaz). Saf/deterministik."""
        return redact(text)

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        principals = self._repo.all_principals()
        return {"principals": len(principals),
                "locked": sum(1 for p in principals if p.locked),
                "audits": self._repo.audit_count(),
                "critical_audits": self._repo.audit_count(severity=Severity.CRITICAL),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return security_contract()

    # ------------------------------------------------------------------ #
    def _decision(self, principal: str, permission: str, allowed: bool, reason: str,
                  locked: bool) -> dict[str, Any]:
        return {"principal": principal, "permission": permission, "allowed": allowed,
                "reason": reason, "locked": locked}

    def _deny(self, principal: str, permission: str, reason: str, *, persist: bool = True) -> None:
        self._metrics["denials"] += 1
        self._audit(SecEvents.DENIED, principal, f"{permission}: {reason}", Severity.WARNING)
        self._emit(SecEvents.DENIED, {"principal": principal, "permission": permission, "reason": reason})

    def _audit(self, kind: str, principal: str, detail: str, severity: str) -> SecurityAudit:
        a = SecurityAudit(kind=kind, principal=principal, detail=redact(detail or ""),
                          severity=severity, at=_now())
        self._repo.append_audit(a)
        self._metrics["events"] += 1
        self._emit(SecEvents.AUDIT, {"kind": kind, "principal": principal, "severity": severity})
        return a

    def _principal_changed(self, actor: str, name: str, change: str) -> None:
        self._audit(SecEvents.PRINCIPAL_CHANGED, name, f"{actor}: {change}", Severity.INFO)
        self._emit(SecEvents.PRINCIPAL_CHANGED, {"actor": actor, "principal": name, "change": change})

    def _require_principal(self, name: str) -> Principal:
        p = self._repo.get_principal(name)
        if p is None:
            raise NotFoundError(f"Principal bulunamadı: {name}")
        return p

    def _authorize_admin(self, actor: str) -> None:
        if not self._cfg.is_admin(actor):
            raise UnauthorizedError(f"'{actor}' güvenlik yönetimi için yetkili değil (admin gerekir)")

    def _validate_roles(self, roles: list) -> None:
        for r in roles:
            if r not in Role.ALL:
                raise ValidationError(f"Geçersiz rol: {r}")

    def _validate_perms(self, perms: list) -> None:
        for p in perms:
            if p not in Permission.ALL:
                raise ValidationError(f"Geçersiz izin: {p}")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
