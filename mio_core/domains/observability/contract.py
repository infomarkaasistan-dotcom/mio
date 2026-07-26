"""MIO Core · Observability Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ObsEvents:
    HEALTH_EVALUATED = "observability.health_evaluated"
    METRIC_RECORDED = "observability.metric_recorded"


OPERATIONS = ("record_metric", "incr", "snapshot", "events", "health", "stats")


def observability_contract() -> dict[str, Any]:
    return {
        "domain": "observability",
        "version": CONTRACT_VERSION,
        "description": "Canlı telemetri: EventBus'ı dinler (olay-tipi sayaçları), özel metrikler ve "
                       "deterministik SAĞLIK roll-up'ı. Çekirdeğe dokunmaz. LLM'den bağımsız.",
        "operations": list(OPERATIONS),
        "events": [ObsEvents.HEALTH_EVALUATED, ObsEvents.METRIC_RECORDED],
        "health_states": ["healthy", "degraded", "unhealthy"],
        "invariants": ["telemetri pasiftir (yan etki yok; yalnız dinler/toplar)",
                       "governance blokları sağlıklı davranıştır (unhealthy saymaz)",
                       "sağlık roll-up'ı deterministiktir (eşik tabanlı)"],
    }
