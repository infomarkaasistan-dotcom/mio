"""MIO Core · Learning Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class LearnEvents:
    OUTCOME_RECORDED = "learning.outcome_recorded"
    KNOWLEDGE_REINFORCED = "learning.knowledge_reinforced"
    BELIEF_REFUTED = "learning.belief_refuted"
    HEURISTIC_EMERGED = "learning.heuristic_emerged"


OPERATIONS = ("record_outcome", "consolidate", "lessons", "history", "stats")


def learning_contract() -> dict[str, Any]:
    return {
        "domain": "learning",
        "version": CONTRACT_VERSION,
        "description": "Sonuçtan (beklenen↔gerçekleşen) deterministik öğrenme: inanç çürütme (E5), bilgi "
                       "güven revizyonu, tekrar eden başarıdan heuristik emergence (Knowledge). LLM'siz.",
        "operations": list(OPERATIONS),
        "events": [LearnEvents.OUTCOME_RECORDED, LearnEvents.KNOWLEDGE_REINFORCED,
                   LearnEvents.BELIEF_REFUTED, LearnEvents.HEURISTIC_EMERGED],
        "invariants": ["öğrenme deterministiktir (kural tabanlı, LLM'siz)",
                       "innate bilgi çürütülmez/silinmez (doktriner korunur)",
                       "emergence yalnız yeterli tekrar eden başarıda tetiklenir"],
    }
