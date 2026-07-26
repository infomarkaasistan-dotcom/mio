"""MIO Core · Finance Operations Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class FinanceEvents:
    TRANSACTION_RECORDED = "finance.transaction_recorded"
    COMMITMENT_REQUESTED = "finance.commitment_requested"
    COMMITMENT_APPROVED = "finance.commitment_approved"
    COMMITMENT_REJECTED = "finance.commitment_rejected"


OPERATIONS = ("record_transaction", "record_commitment", "approve_commitment", "reject_commitment",
              "cash_flow", "category_breakdown", "runway", "list_transactions", "list_commitments", "stats")


def finance_contract() -> dict[str, Any]:
    return {
        "domain": "finance",
        "version": CONTRACT_VERSION,
        "description": "Deterministik finans operasyonu: gelir/gider defteri + nakit akışı/runway + Financial "
                       "Rule (yükümlülük onaysız oluşmaz — Madde 4). LLM'siz; hesaplar deterministik.",
        "operations": list(OPERATIONS),
        "events": [FinanceEvents.TRANSACTION_RECORDED, FinanceEvents.COMMITMENT_REQUESTED,
                   FinanceEvents.COMMITMENT_APPROVED, FinanceEvents.COMMITMENT_REJECTED],
        "commitment_statuses": ["pending_approval", "approved", "rejected", "executed"],
        "invariants": ["finansal yükümlülük onaysız EXECUTED olamaz (Financial Rule, Madde 4)",
                       "nakit akışı/runway deterministiktir (yalnız defterden)",
                       "onay yetkisi owner/Executive'dedir"],
    }
