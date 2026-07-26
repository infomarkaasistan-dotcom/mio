"""MIO Core · Customer Success Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class CSEvents:
    ACCOUNT_ADDED = "customer.account_added"
    TICKET_OPENED = "customer.ticket_opened"
    TICKET_RESOLVED = "customer.ticket_resolved"
    FEEDBACK_RECORDED = "customer.feedback_recorded"
    CHURN_RISK = "customer.churn_risk"


OPERATIONS = ("add_account", "open_ticket", "update_ticket", "record_feedback", "health",
              "list_accounts", "list_tickets", "stats")


def customer_contract() -> dict[str, Any]:
    return {
        "domain": "customer_success",
        "version": CONTRACT_VERSION,
        "description": "Deterministik müşteri başarısı: account + support ticket + CSAT + deterministik health "
                       "score + churn-risk. LLM'siz; hesaplar yalnız kayıtlı veriden.",
        "operations": list(OPERATIONS),
        "events": [CSEvents.ACCOUNT_ADDED, CSEvents.TICKET_OPENED, CSEvents.TICKET_RESOLVED,
                   CSEvents.FEEDBACK_RECORDED, CSEvents.CHURN_RISK],
        "priorities": ["low", "medium", "high"],
        "invariants": ["health score deterministiktir (açık ticket ağırlığı + ortalama CSAT)",
                       "churn-risk = health < eşik (deterministik)",
                       "CSAT 1-5 aralığında doğrulanır"],
    }
