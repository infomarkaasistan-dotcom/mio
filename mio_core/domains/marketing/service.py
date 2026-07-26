"""MIO Core · Marketing & Growth Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Kampanya + metrik biriktirme + türetilen KPI (CTR/CVR/CPA/CPC/ROAS). Hesaplar deterministik; sıfıra bölme
dürüstçe None. LLM ancak içerik/yorum için danışman. authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, MarketingEvents, marketing_contract
from .models import (
    Campaign,
    CampaignStatus,
    MarketingConfig,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import MarketingRepository

logger = logging.getLogger("mio.domain.marketing")


class MarketingDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: MarketingRepository, *, bus=None,
                 config: Optional[MarketingConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or MarketingConfig()
        self._metrics = {"campaigns": 0, "metric_updates": 0}

    # ------------------------------------------------------------------ #
    def create_campaign(self, actor: str, name: str, channel: str, *, budget: float = 0.0,
                        target: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "kampanya adı")
        channel = self._require(channel, "kanal")
        if float(budget) < 0:
            raise ValidationError("budget negatif olamaz")
        camp = Campaign(name=name, channel=channel, budget=round(float(budget), 2), target=target)
        self._repo.put(camp)
        self._metrics["campaigns"] += 1
        self._emit(MarketingEvents.CAMPAIGN_CREATED, {"actor": actor, "id": camp.id, "channel": channel})
        return camp.to_dict()

    def record_metrics(self, actor: str, campaign_id: str, *, impressions: int = 0, clicks: int = 0,
                       conversions: int = 0, spend: float = 0.0, revenue: float = 0.0) -> dict[str, Any]:
        """Metrikleri KÜMÜLATİF ekler (deterministik biriktirme)."""
        self._authorize_writer(actor)
        camp = self._require_campaign(campaign_id)
        for label, v in (("impressions", impressions), ("clicks", clicks),
                         ("conversions", conversions), ("spend", spend), ("revenue", revenue)):
            if float(v) < 0:
                raise ValidationError(f"{label} negatif olamaz")
        camp.impressions += int(impressions)
        camp.clicks += int(clicks)
        camp.conversions += int(conversions)
        camp.spend = round(camp.spend + float(spend), 2)
        camp.revenue = round(camp.revenue + float(revenue), 2)
        if camp.clicks > camp.impressions:
            raise ValidationError("clicks impressions'ı aşamaz")
        if camp.conversions > camp.clicks:
            raise ValidationError("conversions clicks'i aşamaz")
        self._repo.put(camp)
        self._metrics["metric_updates"] += 1
        self._emit(MarketingEvents.METRICS_RECORDED, {"id": campaign_id, "spend": camp.spend})
        return camp.to_dict()

    def set_status(self, actor: str, campaign_id: str, status: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        if status not in CampaignStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        camp = self._require_campaign(campaign_id)
        camp.status = status
        self._repo.put(camp)
        self._emit(MarketingEvents.STATUS_CHANGED, {"id": campaign_id, "status": status})
        return camp.to_dict()

    # -- deterministik analiz -------------------------------------------- #
    def performance(self, actor: str, campaign_id: str) -> dict[str, Any]:
        self._authorize(actor)
        camp = self._require_campaign(campaign_id)
        d = camp.to_dict()
        return {"campaign_id": campaign_id, "channel": camp.channel, "metrics": d["metrics"],
                "kpis": d["kpis"]}

    def channel_breakdown(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        agg: dict[str, dict[str, float]] = {}
        for c in self._repo.all():
            a = agg.setdefault(c.channel, {"spend": 0.0, "revenue": 0.0, "conversions": 0, "campaigns": 0})
            a["spend"] = round(a["spend"] + c.spend, 2)
            a["revenue"] = round(a["revenue"] + c.revenue, 2)
            a["conversions"] += c.conversions
            a["campaigns"] += 1
        for ch, a in agg.items():
            a["roas"] = round(a["revenue"] / a["spend"], 4) if a["spend"] > 0 else None
        return {"channels": agg}

    def list_campaigns(self, actor: str, *, channel: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [c.to_dict() for c in self._repo.all(channel=channel)]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"campaigns": self._repo.count(), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return marketing_contract()

    # ------------------------------------------------------------------ #
    def _require_campaign(self, campaign_id: str) -> Campaign:
        c = self._repo.get(campaign_id)
        if c is None:
            raise NotFoundError(f"Kampanya bulunamadı: {campaign_id}")
        return c

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' pazarlama erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' pazarlama yazımı için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
