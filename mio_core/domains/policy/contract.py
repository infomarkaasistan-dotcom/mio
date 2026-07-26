"""MIO Core · Policy Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class PolicyEvents:
    DEFINED = "policy.defined"
    REMOVED = "policy.removed"
    TOGGLED = "policy.toggled"
    EVALUATED = "policy.evaluated"
    GATED = "policy.gated"            # deny/require_approval verdict'i döndü


OPERATIONS = ("define_policy", "remove_policy", "set_enabled", "evaluate", "list_policies", "stats")


def policy_contract() -> dict[str, Any]:
    return {
        "domain": "policy",
        "version": CONTRACT_VERSION,
        "description": "Deterministik Policy Decision Point: aksiyon+bağlam → tek verdict (allow/deny/"
                       "require_approval). Anayasal innate politikalarla doğar. E4/guardrail'leri tamamlar.",
        "operations": list(OPERATIONS),
        "events": [PolicyEvents.DEFINED, PolicyEvents.REMOVED, PolicyEvents.TOGGLED,
                   PolicyEvents.EVALUATED, PolicyEvents.GATED],
        "effects": ["allow", "deny", "require_approval"],
        "precedence": "deny > require_approval > allow (eşitlikte yüksek priority)",
        "invariants": ["değerlendirme deterministiktir (aynı politika kümesi+bağlam → aynı verdict)",
                       "innate (anayasal) politika değiştirilemez/silinemez",
                       "deny bypass edilemez; require_approval yalnız onayla geçer"],
    }
