"""MIO Core · Capability Adapter Layer — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ConnectorEvents:
    REGISTERED = "connector.registered"
    EXECUTED = "connector.executed"
    UNAVAILABLE = "connector.unavailable"
    REQUIRES_APPROVAL = "connector.requires_approval"
    FAILOVER = "connector.failover"
    FAILED = "connector.failed"


OPERATIONS = ("register", "execute", "available", "providers_for", "capabilities", "overview", "health",
              "stats")


def connector_contract() -> dict[str, Any]:
    return {
        "domain": "connectors",
        "version": CONTRACT_VERSION,
        "description": "Capability Adapter Layer: Executive yalnız execute(capability, request) bilir; Manager "
                       "capability→connector dispatch eder (öncelik+health+failover). Connector yoksa çökmez → "
                       "connector_unavailable. AI connector'lar danışmandır (karar vermez). Yüksek-risk "
                       "capability onay ister (Madde 24).",
        "operations": list(OPERATIONS),
        "events": [ConnectorEvents.REGISTERED, ConnectorEvents.EXECUTED, ConnectorEvents.UNAVAILABLE,
                   ConnectorEvents.REQUIRES_APPROVAL, ConnectorEvents.FAILOVER, ConnectorEvents.FAILED],
        "categories": ["ai", "communication", "productivity", "system"],
        "outcomes": ["executed", "connector_unavailable", "requires_approval", "failed"],
        "invariants": ["Executive isimle değil CAPABILITY ile çağırır (gmail.send değil send_email)",
                       "connector seçimi DETERMİNİSTİK (priority+health; LLM karar verici değil)",
                       "connector yoksa sistem ÇÖKMEZ → connector_unavailable (Madde 8)",
                       "AI connector'lar DANIŞMAN — karar vermez (Madde 1)",
                       "yüksek-risk/geri-alınamaz capability onay ister (Madde 24)",
                       "sağlayıcı hatası → bir sonrakine failover (Madde 28)"],
    }
