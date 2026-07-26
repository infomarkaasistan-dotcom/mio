"""MIO Core · Planning Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class PlanEvents:
    DRAFTED = "planning.drafted"
    STEP_ADDED = "planning.step_added"
    SEQUENCED = "planning.sequenced"
    APPROVED = "planning.approved"
    ABANDONED = "planning.abandoned"


OPERATIONS = ("draft_plan", "add_step", "sequence", "assess", "mark_approved", "abandon",
              "plan_view", "list_plans", "stats")


def planning_contract() -> dict[str, Any]:
    return {
        "domain": "planning",
        "version": CONTRACT_VERSION,
        "description": "Amaca hizmet eden, bağımlılık-sıralı, yetenek-farkında DETERMİNİSTİK plan üretimi; "
                       "fizibilite denetimi. Yürütmez, karar vermez (Execution/E4 ayrı).",
        "operations": list(OPERATIONS),
        "events": [PlanEvents.DRAFTED, PlanEvents.STEP_ADDED, PlanEvents.SEQUENCED, PlanEvents.APPROVED,
                   PlanEvents.ABANDONED],
        "statuses": ["draft", "sequenced", "approved", "abandoned"],
        "invariants": ["sıralama deterministiktir (kararlı topolojik sıralama)",
                       "döngü/çözülemeyen bağımlılık reddedilir (fizibil değil)",
                       "planning yürütmez ve onaylama yetkisi Executive/E4'tedir"],
    }
