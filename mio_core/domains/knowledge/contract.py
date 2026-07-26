"""MIO Core · Knowledge Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class KnowEvents:
    LEARNED = "knowledge.learned"
    RETRIEVED = "knowledge.retrieved"
    APPLIED = "knowledge.applied"
    REINFORCED = "knowledge.reinforced"
    FORGOTTEN = "knowledge.forgotten"


OPERATIONS = ("learn", "what_do_i_know", "apply", "list_knowledge", "reinforce", "forget", "stats")


def knowledge_contract() -> dict[str, Any]:
    return {
        "domain": "knowledge",
        "version": CONTRACT_VERSION,
        "description": "Tipli bilgi (belief/rule/concept/pattern/principle/mental_model/reasoning_template/"
                       "decision_heuristic) yönetimi; bağlama deterministik uygulama (LLM'siz karar üretimi).",
        "operations": list(OPERATIONS),
        "events": [KnowEvents.LEARNED, KnowEvents.RETRIEVED, KnowEvents.APPLIED, KnowEvents.REINFORCED,
                   KnowEvents.FORGOTTEN],
        "knowledge_types": ["belief", "rule", "concept", "pattern", "principle", "mental_model",
                            "reasoning_template", "decision_heuristic"],
        "invariants": ["innate bilgi doktrinerdir (silinemez/değiştirilemez)",
                       "apply deterministiktir (LLM'den bağımsız)",
                       "yaşayan bilgi write-through kalıcıdır"],
    }
