"""MIO Core · Audit & Compliance Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class AuditEvents:
    LOGGED = "audit.logged"
    COMPLIANCE_ASSESSED = "audit.compliance_assessed"
    EXCEPTION_REGISTERED = "audit.exception_registered"


OPERATIONS = ("log", "trail", "assess", "register_exception", "compliance_report", "stats")


def audit_contract() -> dict[str, Any]:
    return {
        "domain": "audit_compliance",
        "version": CONTRACT_VERSION,
        "description": "Platform-geneli DEĞİŞMEZ audit ledger + Constitution Compliance kaydı (Madde 36 / "
                       "§10) sorgulanabilir veri olarak. Security RBAC-audit'ini tamamlar. LLM-bağımsız.",
        "operations": list(OPERATIONS),
        "events": [AuditEvents.LOGGED, AuditEvents.COMPLIANCE_ASSESSED, AuditEvents.EXCEPTION_REGISTERED],
        "compliance_levels": ["fully_compliant", "substantially_compliant", "partially_compliant",
                              "exception_approved", "non_compliant"],
        "invariants": ["audit ledger append-only'dir (değişmez)",
                       "genel uyum seviyesi 'en kötü' kayıtla belirlenir",
                       "compliance kaydı/istisna yazımı admin yetkisi ister ve denetlenir"],
    }
