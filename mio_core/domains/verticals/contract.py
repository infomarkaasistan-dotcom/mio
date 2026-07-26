"""MIO Core · Vertical Domain Brains — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

from .models import VERTICAL_SPECS

CONTRACT_VERSION = "1.0.0"


class VerticalEvents:
    ADVISED = "vertical.advised"
    GUARDRAIL_CHECKED = "vertical.guardrail_checked"
    GUARDRAIL_GATED = "vertical.guardrail_gated"       # bir kapı tetiklendi (onay/red)


OPERATIONS = ("advise", "assess_action", "history", "explain", "stats")


def vertical_contract(name: str, title: str, primary_domain: str) -> dict[str, Any]:
    return {
        "domain": f"vertical.{name}",
        "title": title,
        "version": CONTRACT_VERSION,
        "description": f"{title}: alan-spesifik DETERMİNİSTİK tavsiye + guardrail. Karar VERMEZ "
                       f"(Executive/E4'e gider). Bilgi alanı: {primary_domain}.",
        "operations": list(OPERATIONS),
        "events": [VerticalEvents.ADVISED, VerticalEvents.GUARDRAIL_CHECKED, VerticalEvents.GUARDRAIL_GATED],
        "invariants": ["dikey beyin tavsiye üretir, KARAR VERMEZ (decision_authority=Executive)",
                       "guardrail'ler deterministik ve Anayasa'yı uygular (Financial Rule vb.)",
                       "tavsiye yalnız mevcut bilgi/muhakemeden türetilir (uydurma yok)"],
    }


def verticals_layer_contract() -> dict[str, Any]:
    return {
        "layer": "vertical_domain_brains",
        "version": CONTRACT_VERSION,
        "brains": [s.name for s in VERTICAL_SPECS],
        "count": len(VERTICAL_SPECS),
    }
