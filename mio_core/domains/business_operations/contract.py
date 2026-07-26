"""MIO Core · Business & Operations Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class BizEvents:
    PROCESS_REGISTERED = "business.process_registered"
    PROCESS_ANALYZED = "business.process_analyzed"
    RULE_DEFINED = "business.rule_defined"
    RULES_EVALUATED = "business.rules_evaluated"


OPERATIONS = ("register_process", "analyze_process", "optimize_process", "register_rule", "evaluate",
              "list_processes", "list_rules", "stats")


def business_contract() -> dict[str, Any]:
    return {
        "domain": "business_operations",
        "version": CONTRACT_VERSION,
        "description": "Deterministik iş/operasyon: süreç registry + darboğaz analizi + optimizasyon + iş "
                       "kuralı motoru (koşul→aksiyon). LLM'siz; öneriler yalnız girilen veriden.",
        "operations": list(OPERATIONS),
        "events": [BizEvents.PROCESS_REGISTERED, BizEvents.PROCESS_ANALYZED, BizEvents.RULE_DEFINED,
                   BizEvents.RULES_EVALUATED],
        "invariants": ["süreç analizi ve kural değerlendirmesi deterministiktir",
                       "darboğaz = tek adımın toplam süredeki oranı eşik üstü",
                       "kural motoru priority sırasına göre deterministik aksiyon üretir (karar değil, öneri)"],
    }
