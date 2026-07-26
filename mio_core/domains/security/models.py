"""MIO Core · Security Domain — modeller, RBAC, config (production-grade), LLM-BAĞIMSIZ.

Merkezî kimlik + yetki (RBAC) + güvenlik denetim izi + secret redaksiyonu + kilitleme. Her domain'in kendi
yetki-config'i vardır; bu domain sistem-geneli RBAC ve güvenlik olay denetimini merkezîleştirir. Anayasa:
'.env / secret asla loglanmaz' → `redact()` bunu birinci-sınıf yetenek yapar."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


class Permission:
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"
    FINANCIAL = "financial"
    SECURITY_ADMIN = "security_admin"
    ALL = {READ, WRITE, EXECUTE, ADMIN, FINANCIAL, SECURITY_ADMIN}


class Role:
    OWNER = "owner"            # süper kullanıcı (tüm izinler)
    EXECUTIVE = "executive"
    OPERATIONS = "operations"
    SECURITY = "security"
    BRAIN = "brain"           # alan beyni (okuma + tavsiye)
    ALL = {OWNER, EXECUTIVE, OPERATIONS, SECURITY, BRAIN}


ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.OWNER: set(Permission.ALL),
    Role.EXECUTIVE: {Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.ADMIN,
                     Permission.FINANCIAL},
    Role.OPERATIONS: {Permission.READ, Permission.WRITE, Permission.EXECUTE},
    Role.SECURITY: {Permission.READ, Permission.SECURITY_ADMIN},
    Role.BRAIN: {Permission.READ},
}


class Severity:
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SecurityError(Exception):
    """Security Domain temel hatası."""


class ValidationError(SecurityError):
    pass


class UnauthorizedError(SecurityError):
    pass


class NotFoundError(SecurityError):
    pass


@dataclass
class Principal:
    name: str
    roles: list[str] = field(default_factory=list)
    grants: list[str] = field(default_factory=list)     # role dışı doğrudan verilen izinler
    locked: bool = False
    failed_checks: int = 0

    def effective_permissions(self) -> set[str]:
        perms: set[str] = set(self.grants)
        for r in self.roles:
            perms |= ROLE_PERMISSIONS.get(r, set())
        return perms

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "roles": list(self.roles), "grants": list(self.grants),
                "locked": self.locked, "failed_checks": self.failed_checks,
                "effective_permissions": sorted(self.effective_permissions())}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Principal":
        return cls(name=d["name"], roles=list(d.get("roles") or []), grants=list(d.get("grants") or []),
                   locked=bool(d.get("locked", False)), failed_checks=int(d.get("failed_checks", 0)))


@dataclass
class SecurityAudit:
    kind: str
    principal: str = ""
    detail: str = ""
    severity: str = Severity.INFO
    at: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:16])

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "principal": self.principal, "detail": self.detail,
                "severity": self.severity, "at": self.at}


# --- Secret redaksiyonu (Anayasa: secret asla loglanmaz) ------------------- #
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),                              # OpenAI-tarzı anahtar
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd|bearer)\b\s*[:=]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),                          # uzun jeton/hex/base64
]
_REDACTED = "***REDACTED***"


def redact(text: str) -> str:
    """Secret benzeri desenleri maskeler — deterministik. .env/anahtar loglamayı önler (Anayasa)."""
    out = text or ""
    for pat in _SECRET_PATTERNS:
        out = pat.sub(_REDACTED, out)
    return out


@dataclass
class SecurityConfig:
    lockout_threshold: int = 5           # ardışık başarısız yetki kontrolü → kilit
    history_limit: int = 200
    admin_actors: set = field(default_factory=lambda: {"owner", "Executive", "Security"})

    def is_admin(self, actor: str) -> bool:
        return actor == "owner" or actor in self.admin_actors


def default_principals() -> list[Principal]:
    """Doğuştan kimlikler: owner süper kullanıcı + çekirdek roller + 14 alan/işlev beyni."""
    brains = ["Business", "Finance", "Marketing", "Sales", "Product", "Engineering", "Knowledge",
              "Security", "Operations", "Workflow", "Learning", "Communication", "Reasoning", "Planning",
              "Memory", "Perception"]
    principals = [
        Principal(name="owner", roles=[Role.OWNER]),
        Principal(name="Executive", roles=[Role.EXECUTIVE]),
        Principal(name="Operations", roles=[Role.OPERATIONS]),
        Principal(name="Security", roles=[Role.SECURITY]),
    ]
    seen = {p.name for p in principals}
    for b in brains:
        if b not in seen:
            principals.append(Principal(name=b, roles=[Role.BRAIN]))
    return principals


__all__ = [
    "Permission", "Role", "ROLE_PERMISSIONS", "Severity", "Principal", "SecurityAudit",
    "redact", "SecurityConfig", "default_principals",
    "SecurityError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
