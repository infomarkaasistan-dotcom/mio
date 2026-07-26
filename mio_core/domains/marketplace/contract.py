"""MIO Core · Marketplace / Ecosystem Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class MarketplaceEvents:
    LISTING_SUBMITTED = "marketplace.listing_submitted"
    LISTING_APPROVED = "marketplace.listing_approved"
    LISTING_REJECTED = "marketplace.listing_rejected"
    INSTALLED = "marketplace.installed"
    INSTALL_FAILED = "marketplace.install_failed"
    NO_CONNECTOR = "marketplace.no_connector"
    REMOVED = "marketplace.removed"


OPERATIONS = ("submit_listing", "check_compatibility", "approve", "reject", "install", "remove",
              "get_listing", "list_listings", "installers", "stats")


def marketplace_contract() -> dict[str, Any]:
    return {
        "domain": "marketplace",
        "version": CONTRACT_VERSION,
        "description": "Yayın (listing) registry + yayıncı/sürüm/imza + DETERMİNİSTİK uyumluluk & allowlist "
                       "politikası + inceleme/kurulum durum makinesi. Denetlenmemiş üçüncü-taraf yetenek "
                       "platforma sokulamaz; kurulum onay ister (Madde 24). Gerçek indirme/kurulum adapter'a "
                       "delege; yoksa no_connector.",
        "operations": list(OPERATIONS),
        "events": [MarketplaceEvents.LISTING_SUBMITTED, MarketplaceEvents.LISTING_APPROVED,
                   MarketplaceEvents.LISTING_REJECTED, MarketplaceEvents.INSTALLED,
                   MarketplaceEvents.INSTALL_FAILED, MarketplaceEvents.NO_CONNECTOR,
                   MarketplaceEvents.REMOVED],
        "listing_kinds": ["capability", "plugin", "model", "dataset", "mcp_server"],
        "statuses": ["submitted", "approved", "rejected", "installed", "removed"],
        "compatibility_policy": "deterministik: yayıncı/kaynak allowlist + imza + geçerli tür",
        "invariants": ["denetlenmemiş/güvenilmez üçüncü-taraf yetenek onaylanamaz (otomatik reddedilir)",
                       "kurulum yalnız APPROVED listing için; onay owner/Executive (Madde 24)",
                       "uyumluluk değerlendirmesi DETERMİNİSTİK (LLM karar verici değil)",
                       "gerçek indirme/kurulum adapter'a delege; yoksa no_connector (uydurma YOK — Madde 8)",
                       "yaşam-döngüsü geçişleri kısıtlı (rejected/removed terminaldir)"],
    }
