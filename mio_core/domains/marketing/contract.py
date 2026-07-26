"""MIO Core · Marketing & Growth Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class MarketingEvents:
    CAMPAIGN_CREATED = "marketing.campaign_created"
    METRICS_RECORDED = "marketing.metrics_recorded"
    STATUS_CHANGED = "marketing.status_changed"


OPERATIONS = ("create_campaign", "record_metrics", "set_status", "performance", "channel_breakdown",
              "list_campaigns", "stats")


def marketing_contract() -> dict[str, Any]:
    return {
        "domain": "marketing",
        "version": CONTRACT_VERSION,
        "description": "Deterministik pazarlama: kampanya (kanal/bütçe) + metrik biriktirme + türetilen KPI "
                       "(CTR/CVR/CPA/CPC/ROAS). LLM'siz; sıfıra bölme dürüstçe None (uydurma yok).",
        "operations": list(OPERATIONS),
        "events": [MarketingEvents.CAMPAIGN_CREATED, MarketingEvents.METRICS_RECORDED,
                   MarketingEvents.STATUS_CHANGED],
        "kpis": ["ctr_pct", "cvr_pct", "cpc", "cpa", "roas", "budget_used_pct"],
        "invariants": ["KPI'lar deterministiktir (aynı metrik → aynı KPI)",
                       "sıfıra bölme None döner (uydurma yok)",
                       "metrikler biriktirilir (kümülatif)"],
    }
