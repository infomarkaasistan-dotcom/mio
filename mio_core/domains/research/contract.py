"""MIO Core · Research Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ResearchEvents:
    INQUIRY_STARTED = "research.inquiry_started"
    FINDING_ADDED = "research.finding_added"
    FINDING_VERIFIED = "research.finding_verified"
    SYNTHESIZED = "research.synthesized"


OPERATIONS = ("start_inquiry", "add_finding", "verify_finding", "synthesize", "report",
              "list_inquiries", "stats")


def research_contract() -> dict[str, Any]:
    return {
        "domain": "research",
        "version": CONTRACT_VERSION,
        "description": "Deterministik araştırma: soruşturma + bulgu (kaynak/güvenilirlik) + DETERMİNİSTİK "
                       "sentez (corroboration/doğrulama). LLM prose-sentezi danışman; yapısal sentez çekirdekte.",
        "operations": list(OPERATIONS),
        "events": [ResearchEvents.INQUIRY_STARTED, ResearchEvents.FINDING_ADDED,
                   ResearchEvents.FINDING_VERIFIED, ResearchEvents.SYNTHESIZED],
        "credibility_levels": ["low", "medium", "high"],
        "invariants": ["sentez deterministiktir (corroboration = distinct kaynak sayısı)",
                       "kanıt uydurulmaz (yalnız girilen bulgulardan)",
                       "tek-kaynak/doğrulanmamış bulgular açıkça işaretlenir"],
    }
