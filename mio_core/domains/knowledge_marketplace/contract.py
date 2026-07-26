"""MIO Core · Knowledge Marketplace Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class KnowledgeMarketEvents:
    PACK_SUBMITTED = "kmarket.pack_submitted"
    PACK_APPROVED = "kmarket.pack_approved"
    PACK_REJECTED = "kmarket.pack_rejected"
    IMPORTED = "kmarket.imported"
    IMPORT_FAILED = "kmarket.import_failed"
    NO_CONNECTOR = "kmarket.no_connector"
    REMOVED = "kmarket.removed"


OPERATIONS = ("submit_pack", "check_compatibility", "approve", "reject", "import_pack", "remove",
              "get_pack", "list_packs", "sources", "stats")


def knowledge_market_contract() -> dict[str, Any]:
    return {
        "domain": "knowledge_marketplace",
        "version": CONTRACT_VERSION,
        "description": "Bilgi paketi registry + yayıncı/sürüm/lisans/checksum + DETERMİNİSTİK kalite & lisans & "
                       "allowlist politikası + import durum makinesi + provenance etiketi. Denetlenmemiş bilgi "
                       "Knowledge Domain'e sokulamaz; import onay ister (Madde 24). Gerçek indirme/import "
                       "adapter'a delege; yoksa no_connector.",
        "operations": list(OPERATIONS),
        "events": [KnowledgeMarketEvents.PACK_SUBMITTED, KnowledgeMarketEvents.PACK_APPROVED,
                   KnowledgeMarketEvents.PACK_REJECTED, KnowledgeMarketEvents.IMPORTED,
                   KnowledgeMarketEvents.IMPORT_FAILED, KnowledgeMarketEvents.NO_CONNECTOR,
                   KnowledgeMarketEvents.REMOVED],
        "pack_kinds": ["fact_set", "ontology", "prompt_lib", "skill"],
        "statuses": ["submitted", "approved", "rejected", "imported", "removed"],
        "compatibility_policy": "deterministik: yayıncı/kaynak allowlist + izinli lisans + checksum + geçerli tür",
        "invariants": ["denetlenmemiş/lisanssız bilgi onaylanamaz (otomatik reddedilir)",
                       "import yalnız APPROVED pack için; onay owner/Executive (Madde 24)",
                       "uyumluluk değerlendirmesi DETERMİNİSTİK (LLM karar verici değil)",
                       "import edilen bilgi provenance (kaynak/lisans/sürüm) etiketiyle işaretlenir",
                       "gerçek indirme/import adapter'a delege; yoksa no_connector (uydurma YOK — Madde 8)"],
    }
