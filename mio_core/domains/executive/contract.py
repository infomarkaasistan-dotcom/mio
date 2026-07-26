"""MIO Core · Executive Domain — Public Contract (versioned, Bounded Context §4 + Platform Invariant §2).

Domain'ler yalnız bu sözleşme üzerinden konuşur. Sürüm ve geriye-uyum burada tanımlıdır."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ExecEvents:
    """Executive Domain'in yayınladığı Public Event'ler (versiyonlu)."""
    GOAL_SET = "executive.goal.set"
    GOAL_ABANDONED = "executive.goal.abandoned"
    DECISION_MADE = "executive.decision.made"
    REVIEW_COMPLETED = "executive.review.completed"
    MISSION_SET = "executive.mission.set"
    PURPOSE_SET = "executive.purpose.set"


# Domain'in dışa açtığı Public Operation'lar (API yüzeyi).
OPERATIONS = (
    "set_goal", "abandon_goal", "decide", "review", "introspect", "status",
    "set_mission", "set_purpose", "metrics",
)


def executive_contract() -> dict[str, Any]:
    return {
        "domain": "executive",
        "version": CONTRACT_VERSION,
        "description": "Stratejik karar/planlama/koordinasyon/delegasyon/hedef yönetimi/orkestrasyon.",
        "operations": list(OPERATIONS),
        "events": [ExecEvents.GOAL_SET, ExecEvents.GOAL_ABANDONED, ExecEvents.DECISION_MADE,
                   ExecEvents.REVIEW_COMPLETED, ExecEvents.MISSION_SET, ExecEvents.PURPOSE_SET],
        "wraps_core": ["E1 State", "E2 Goal", "E3 Review", "E4 Governance", "E5 Cognitive"],
        "invariants": ["Executive dış sistemle doğrudan konuşmaz", "LLM karar-verici değildir",
                       "insan nihai otoritedir", "her karar audit'lenir"],
    }
