"""MIO Core · Sales & CRM Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class SalesEvents:
    CONTACT_ADDED = "sales.contact_added"
    OPPORTUNITY_ADDED = "sales.opportunity_added"
    STAGE_CHANGED = "sales.stage_changed"
    QUALIFIED = "sales.qualified"


OPERATIONS = ("add_contact", "add_opportunity", "advance_stage", "pipeline", "qualify",
              "list_contacts", "list_opportunities", "stats")


def sales_contract() -> dict[str, Any]:
    return {
        "domain": "sales",
        "version": CONTRACT_VERSION,
        "description": "Deterministik satış/CRM: contact + opportunity/pipeline (stage) + ağırlıklı pipeline "
                       "metrikleri + lead qualification. LLM'siz; hesaplar deterministik.",
        "operations": list(OPERATIONS),
        "events": [SalesEvents.CONTACT_ADDED, SalesEvents.OPPORTUNITY_ADDED, SalesEvents.STAGE_CHANGED,
                   SalesEvents.QUALIFIED],
        "stages": ["lead", "qualified", "proposal", "negotiation", "won", "lost"],
        "invariants": ["pipeline metrikleri deterministiktir (ağırlık = stage olasılığı)",
                       "kazanma oranı = won / (won + lost)",
                       "lead qualification kural-tabanlıdır (öneri; karar Executive'de)"],
    }
