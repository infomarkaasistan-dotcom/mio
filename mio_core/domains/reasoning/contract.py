"""MIO Core · Reasoning Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class ReasonEvents:
    DEDUCED = "reasoning.deduced"
    DELIBERATED = "reasoning.deliberated"
    CONSISTENCY_CHECKED = "reasoning.consistency_checked"


OPERATIONS = ("deduce", "deliberate", "consistency_report", "explain", "history", "stats")


def reasoning_contract() -> dict[str, Any]:
    return {
        "domain": "reasoning",
        "version": CONTRACT_VERSION,
        "description": "Deterministik çıkarım: bilgi + inanç + muhakeme şablonu birleşiminden açıklanabilir "
                       "sonuç (LLM'den bağımsız). Her muhakeme denetlenebilir iz olarak kalıcı.",
        "operations": list(OPERATIONS),
        "events": [ReasonEvents.DEDUCED, ReasonEvents.DELIBERATED, ReasonEvents.CONSISTENCY_CHECKED],
        "kinds": ["deduce", "deliberate", "consistency"],
        "invariants": ["çıkarım deterministiktir (aynı girdi → aynı sonuç)",
                       "kanıt uydurulmaz (yalnız mevcut bilgi/inançtan)",
                       "her muhakeme iz olarak kalıcı (açıklanabilirlik)"],
    }
