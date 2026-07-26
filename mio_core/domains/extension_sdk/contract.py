"""MIO Core · Extension SDK Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ExtensionEvents:
    REGISTERED = "extension.registered"
    VALIDATED = "extension.validated"
    REJECTED = "extension.rejected"
    ENABLED = "extension.enabled"
    DISABLED = "extension.disabled"
    INVOKED = "extension.invoked"
    INVOKE_FAILED = "extension.invoke_failed"
    NO_CONNECTOR = "extension.no_connector"


OPERATIONS = ("register_extension", "validate", "enable", "disable", "invoke", "get_extension",
              "list_extensions", "hosts", "permissions_catalog", "stats")


def extension_contract() -> dict[str, Any]:
    return {
        "domain": "extension_sdk",
        "version": CONTRACT_VERSION,
        "description": "Uzantı manifest registry + DETERMİNİSTİK manifest & izin-kapsamı doğrulama (yayıncı/imza "
                       "allowlist + istenen izinlerin grantable-allowlist uyumu) + uzantı yaşam-döngüsü. "
                       "Denetlenmemiş/aşırı-izinli uzantı platforma sokulamaz; etkinleştirme onay ister "
                       "(Madde 24). Uzantı çalıştırma host sandbox adapter'a delege; yoksa no_connector.",
        "operations": list(OPERATIONS),
        "events": [ExtensionEvents.REGISTERED, ExtensionEvents.VALIDATED, ExtensionEvents.REJECTED,
                   ExtensionEvents.ENABLED, ExtensionEvents.DISABLED, ExtensionEvents.INVOKED,
                   ExtensionEvents.INVOKE_FAILED, ExtensionEvents.NO_CONNECTOR],
        "extension_kinds": ["tool", "hook", "panel", "workflow", "connector"],
        "statuses": ["registered", "validated", "enabled", "disabled", "rejected"],
        "validation_policy": "deterministik: yayıncı/imza allowlist + istenen izinlerin grantable-allowlist uyumu",
        "invariants": ["denetlenmemiş/aşırı-izinli uzantı doğrulanamaz/etkinleştirilemez (otomatik reddedilir)",
                       "etkinleştirme yalnız VALIDATED uzantı için; onay owner/Executive (Madde 24)",
                       "en-az-yetki: yalnız istenen ve grantable-allowlist'teki izinler verilir",
                       "manifest/izin doğrulaması DETERMİNİSTİK (LLM karar verici değil)",
                       "uzantı çalıştırma host sandbox adapter'a delege; yoksa no_connector (uydurma YOK — Madde 8)"],
    }
