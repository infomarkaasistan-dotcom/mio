"""MIO Core · Autonomous Operations Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class AutoOpsEvents:
    RULE_ADDED = "autoops.rule_added"
    PROPOSAL_CREATED = "autoops.proposal_created"     # Executive'e öneri (recommendation)
    AUTO_EXECUTED = "autoops.auto_executed"           # kapalı-döngü allowlisted güvenli aksiyon
    APPROVED = "autoops.approved"
    REJECTED = "autoops.rejected"
    EXECUTED = "autoops.executed"
    FAILED = "autoops.failed"
    NO_CONNECTOR = "autoops.no_connector"


OPERATIONS = ("add_rule", "observe", "approve_proposal", "reject_proposal", "get_proposal",
              "list_proposals", "list_rules", "actions", "stats")


def auto_ops_contract() -> dict[str, Any]:
    return {
        "domain": "autonomous_operations",
        "version": CONTRACT_VERSION,
        "description": "Operasyon kuralı registry + DETERMİNİSTİK tetik/koşul değerlendirme + öneri "
                       "(recommendation) üretimi + aksiyon durum makinesi. Otonom aksiyon KARAR VERMEZ; "
                       "Executive'e öneri üretir; uygulama Madde 24 onayıyla. Kapalı-döngü YALNIZ allowlisted "
                       "güvenli aksiyonlarda (opt-in). Aksiyon yürütme adapter'a delege; yoksa no_connector.",
        "operations": list(OPERATIONS),
        "events": [AutoOpsEvents.RULE_ADDED, AutoOpsEvents.PROPOSAL_CREATED, AutoOpsEvents.AUTO_EXECUTED,
                   AutoOpsEvents.APPROVED, AutoOpsEvents.REJECTED, AutoOpsEvents.EXECUTED,
                   AutoOpsEvents.FAILED, AutoOpsEvents.NO_CONNECTOR],
        "severities": ["info", "warning", "critical"],
        "comparators": [">", ">=", "<", "<=", "==", "!="],
        "proposal_statuses": ["requires_approval", "executed", "rejected", "failed", "no_connector"],
        "invariants": ["otonom aksiyon KARAR VERMEZ; Executive'e öneri üretir (autonomy ≠ otonom karar)",
                       "öneri uygulaması onay ister (Madde 24; owner/Executive)",
                       "kapalı-döngü otomasyon YALNIZ allowlisted güvenli aksiyon + closed_loop açıkken",
                       "tetik/koşul değerlendirmesi DETERMİNİSTİK (LLM karar verici değil)",
                       "aksiyon yürütme adapter'a delege; yoksa no_connector (uydurma sonuç YOK — Madde 8)"],
    }
