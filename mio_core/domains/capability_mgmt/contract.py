"""MIO Core · Capability Management Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class CapEvents:
    REGISTERED = "capability.registered"
    MATURITY_CHANGED = "capability.maturity_changed"
    CONNECTED = "capability.connected"
    SELECTED = "capability.selected"


OPERATIONS = ("register", "describe", "list_capabilities", "set_maturity", "deprecate", "retire",
              "set_connected", "select_best", "usable", "lifecycle_history", "stats")


def capability_mgmt_contract() -> dict[str, Any]:
    return {
        "domain": "capability_management",
        "version": CONTRACT_VERSION,
        "description": "Çekirdek CapabilityRegistry'yi saran governance: maturity yaşam-döngüsü (§7), sürümlü "
                       "sözleşme (Madde 29), yetenek seçimi ve evolution denetimi (Madde 26). LLM-bağımsız.",
        "operations": list(OPERATIONS),
        "events": [CapEvents.REGISTERED, CapEvents.MATURITY_CHANGED, CapEvents.CONNECTED, CapEvents.SELECTED],
        "maturity_levels": ["experimental", "preview", "stable", "production", "deprecated", "retired"],
        "invariants": ["maturity geçişleri §7 kurallarına uyar (retired terminaldir)",
                       "yetenek seçimi deterministiktir (maturity sırası + priority)",
                       "yalnız USABLE maturity + connected yetenek yürütmeye seçilir",
                       "çekirdek registry sarılır, değiştirilmez (Madde 15/16)"],
    }
