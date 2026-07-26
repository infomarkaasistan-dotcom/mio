"""MIO Core · Resource & Runtime Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ResourceEvents:
    SNAPSHOT = "resources.snapshot"
    BUDGET_SET = "resources.budget_set"
    BUDGET_CONSUMED = "resources.budget_consumed"
    BUDGET_EXCEEDED = "resources.budget_exceeded"
    BOTTLENECK = "resources.bottleneck"


OPERATIONS = ("snapshot", "set_budget", "consume", "can_afford", "reset_budget", "budget_status",
              "bottlenecks", "recommendations", "stats")


def resources_contract() -> dict[str, Any]:
    return {
        "domain": "resource_runtime",
        "version": CONTRACT_VERSION,
        "description": "Resource Awareness (Madde 30): kaynak snapshot + API/Token/Cost bütçe + deterministik "
                       "darboğaz/yükseltme analizi. Executive kaynak-farkında karar için sorgular. LLM-bağımsız.",
        "operations": list(OPERATIONS),
        "events": [ResourceEvents.SNAPSHOT, ResourceEvents.BUDGET_SET, ResourceEvents.BUDGET_CONSUMED,
                   ResourceEvents.BUDGET_EXCEEDED, ResourceEvents.BOTTLENECK],
        "invariants": ["snapshot yalnız probe'un verdiği GERÇEK veriden (uydurma yok; eksik alan atlanır)",
                       "bütçe tüketimi ve darboğaz analizi deterministiktir",
                       "bütçe aşımı görünür (event); can_afford karar-öncesi deterministik kontrol"],
    }
