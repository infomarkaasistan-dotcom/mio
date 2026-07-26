"""MIO Core · Perception Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class PerceiveEvents:
    PERCEIVED = "perception.perceived"
    ATTENTION = "perception.attention"       # yüksek belirginlik → dikkat tetiği
    ROUTED = "perception.routed"


OPERATIONS = ("perceive", "recent", "attention", "explain", "stats")


def perception_contract() -> dict[str, Any]:
    return {
        "domain": "perception",
        "version": CONTRACT_VERSION,
        "description": "Diyalog-dışı dış sinyalleri DETERMİNİSTİK tipli percept'lere normalize eder ve bilişe "
                       "yönlendirir (E5 belief / Memory epizodik / Attention). LLM'den bağımsız.",
        "operations": list(OPERATIONS),
        "events": [PerceiveEvents.PERCEIVED, PerceiveEvents.ATTENTION, PerceiveEvents.ROUTED],
        "percept_kinds": ["observation", "event", "metric", "signal", "alert"],
        "invariants": ["normalizasyon deterministiktir (türe göre belirginlik)",
                       "kanıt uydurulmaz (yalnız gelen sinyalden)",
                       "yüksek belirginlik dikkat tetikler; gözlemler E5 inanç oluşumuna gider"],
    }
