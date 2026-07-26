"""MIO Core · Software Engineering Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class SEEvents:
    ANALYZED = "software.analyzed"
    QUALITY_GATE = "software.quality_gate"
    ARTIFACT_REGISTERED = "software.artifact_registered"
    TASK_CREATED = "software.task_created"
    TASK_UPDATED = "software.task_updated"


OPERATIONS = ("analyze_code", "quality_gate", "register_artifact", "create_task", "update_task_status",
              "list_tasks", "list_artifacts", "stats")


def software_contract() -> dict[str, Any]:
    return {
        "domain": "software_engineering",
        "version": CONTRACT_VERSION,
        "description": "Deterministik statik analiz (stdlib ast) + Anayasa 'placeholder yok' quality gate + "
                       "artifact/engineering-task registry. Kod-üretimi LLM danışmana; doğrulama deterministik.",
        "operations": list(OPERATIONS),
        "events": [SEEvents.ANALYZED, SEEvents.QUALITY_GATE, SEEvents.ARTIFACT_REGISTERED,
                   SEEvents.TASK_CREATED, SEEvents.TASK_UPDATED],
        "task_kinds": ["feature", "bug", "refactor", "test", "docs"],
        "invariants": ["analiz deterministiktir (aynı kaynak → aynı rapor)",
                       "quality gate placeholder/stub/TODO'yu reddeder (Anayasa)",
                       "kod-üretimi karar değildir (LLM danışman); doğrulama çekirdekte"],
    }
