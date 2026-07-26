"""MIO Core · Security Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class SecEvents:
    CHECK = "security.check"
    DENIED = "security.denied"
    PRINCIPAL_CHANGED = "security.principal_changed"
    LOCKED = "security.locked"
    UNLOCKED = "security.unlocked"
    AUDIT = "security.audit"


OPERATIONS = ("check", "register_principal", "grant", "revoke", "assign_role", "lock", "unlock",
              "record_event", "audit_trail", "redact", "stats")


def security_contract() -> dict[str, Any]:
    return {
        "domain": "security",
        "version": CONTRACT_VERSION,
        "description": "Merkezî RBAC + güvenlik denetim izi + secret redaksiyonu + kilitleme. Deterministik "
                       "yetki kararı; append-only audit. Anayasa: secret asla loglanmaz (redact).",
        "operations": list(OPERATIONS),
        "events": [SecEvents.CHECK, SecEvents.DENIED, SecEvents.PRINCIPAL_CHANGED, SecEvents.LOCKED,
                   SecEvents.UNLOCKED, SecEvents.AUDIT],
        "roles": ["owner", "executive", "operations", "security", "brain"],
        "permissions": ["read", "write", "execute", "admin", "financial", "security_admin"],
        "invariants": ["yetki kararı deterministiktir (RBAC: rol izinleri ∪ doğrudan grant'ler)",
                       "denetim izi append-only'dir",
                       "ardışık başarısız kontrol eşiği aşınca principal kilitlenir",
                       "redact secret desenlerini maskeler (Anayasa: secret loglanmaz)"],
    }
