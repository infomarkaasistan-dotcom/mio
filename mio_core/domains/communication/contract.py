"""MIO Core · Communication Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class CommEvents:
    TURN_RECEIVED = "communication.turn_received"
    REPLIED = "communication.replied"
    INTENT_CLASSIFIED = "communication.intent_classified"


OPERATIONS = ("converse", "classify", "register_handler", "history", "conversations", "stats")


def communication_contract() -> dict[str, Any]:
    return {
        "domain": "communication",
        "version": CONTRACT_VERSION,
        "description": "Çok-turlu kalıcı diyalog + DETERMİNİSTİK niyet sınıflandırma + yanıt kompozisyonu. "
                       "LLM yalnız opsiyonel danışman; erişilemezse deterministik yollarla çalışır.",
        "operations": list(OPERATIONS),
        "events": [CommEvents.TURN_RECEIVED, CommEvents.INTENT_CLASSIFIED, CommEvents.REPLIED],
        "intents": ["greeting", "status", "query_knowledge", "goal", "plan", "reason", "unknown"],
        "response_sources": ["handler", "advisor", "fallback"],
        "invariants": ["niyet sınıflandırma deterministiktir (kural tabanlı)",
                       "LLM danışman opsiyoneldir; yokluğunda dürüst geri-dönüş verilir",
                       "Communication karar vermez (niyeti çekirdeğe yönlendirir)"],
    }
