"""MIO Core · Marketing & Growth Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Deterministik pazarlama: kampanya (kanal/bütçe) + metrik biriktirme + türetilen KPI (CTR/CVR/CPA/CPC/ROAS).
Advisory Marketing Brain'in operasyonel karşılığı; hesaplar deterministik, sıfıra bölme dürüstçe None."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CampaignStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    ALL = {DRAFT, ACTIVE, PAUSED, ENDED}


class MarketingError(Exception):
    """Marketing & Growth Domain temel hatası."""


class ValidationError(MarketingError):
    pass


class UnauthorizedError(MarketingError):
    pass


class NotFoundError(MarketingError):
    pass


def _ratio(num: float, den: float, *, pct: bool = False, nd: int = 4) -> Any:
    """Sıfıra bölme dürüstçe None (uydurma yok)."""
    if den == 0:
        return None
    v = num / den
    return round(v * 100, nd) if pct else round(v, nd)


@dataclass
class Campaign:
    name: str
    channel: str
    budget: float = 0.0
    target: str = ""
    status: str = CampaignStatus.ACTIVE
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend: float = 0.0
    revenue: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def kpis(self) -> dict[str, Any]:
        return {
            "ctr_pct": _ratio(self.clicks, self.impressions, pct=True),          # tıklama oranı
            "cvr_pct": _ratio(self.conversions, self.clicks, pct=True),          # dönüşüm oranı
            "cpc": _ratio(self.spend, self.clicks),                             # tıklama başı maliyet
            "cpa": _ratio(self.spend, self.conversions),                       # edinme başı maliyet
            "roas": _ratio(self.revenue, self.spend),                          # reklam harcaması getirisi
            "budget_used_pct": _ratio(self.spend, self.budget, pct=True) if self.budget else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "channel": self.channel, "budget": self.budget,
                "target": self.target, "status": self.status,
                "metrics": {"impressions": self.impressions, "clicks": self.clicks,
                            "conversions": self.conversions, "spend": round(self.spend, 2),
                            "revenue": round(self.revenue, 2)},
                "kpis": self.kpis(), "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Campaign":
        m = d.get("metrics", {})
        return cls(name=d["name"], channel=d["channel"], budget=float(d.get("budget", 0.0)),
                   target=d.get("target", ""), status=d.get("status", CampaignStatus.ACTIVE),
                   impressions=int(m.get("impressions", 0)), clicks=int(m.get("clicks", 0)),
                   conversions=int(m.get("conversions", 0)), spend=float(m.get("spend", 0.0)),
                   revenue=float(m.get("revenue", 0.0)), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class MarketingConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Marketing", "Sales", "Operations", "Business", "Planning", "Reasoning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Marketing", "Operations"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "CampaignStatus", "Campaign", "MarketingConfig",
    "MarketingError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
