"""MIO Core · Resource & Runtime Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Resource Awareness (Madde 30): CPU/RAM/GPU/Disk snapshot + API/Token/Cost bütçe takibi + deterministik
darboğaz/yükseltme analizi. Executive 'doğru' kadar 'verimli' çözümü de seçebilsin diye kaynakları sorgular.
Çekirdek hardware adaptörünü (probe) sarar; kendisi ağ/donanım erişimi yapmaz."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResourceError(Exception):
    """Resource & Runtime Domain temel hatası."""


class ValidationError(ResourceError):
    pass


class UnauthorizedError(ResourceError):
    pass


class NotFoundError(ResourceError):
    pass


@dataclass
class Budget:
    """Bir kaynak bütçesi (API çağrısı / token / maliyet / latency vb.)."""
    name: str
    limit: float
    consumed: float = 0.0
    unit: str = "units"
    updated_at: str = field(default_factory=_now)

    @property
    def remaining(self) -> float:
        return round(self.limit - self.consumed, 6)

    @property
    def within(self) -> bool:
        return self.consumed <= self.limit

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "limit": self.limit, "consumed": round(self.consumed, 6),
                "remaining": self.remaining, "within_budget": self.within, "unit": self.unit,
                "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Budget":
        return cls(name=d["name"], limit=float(d["limit"]), consumed=float(d.get("consumed", 0.0)),
                   unit=d.get("unit", "units"), updated_at=d.get("updated_at") or _now())


@dataclass
class ResourceConfig:
    # Darboğaz eşikleri (deterministik analiz)
    ram_bottleneck_free_ratio: float = 0.12    # boş RAM oranı bunun altındaysa darboğaz
    cpu_bottleneck_percent: float = 90.0       # cpu_percent bunun üstündeyse darboğaz
    disk_bottleneck_free_gb: float = 5.0       # boş disk bunun altındaysa darboğaz
    snapshot_history: int = 50
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Planning", "Workflow", "Engineering", "Reasoning"})
    admin_actors: set = field(default_factory=lambda: {"owner", "Executive", "Operations"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Workflow", "Execution"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_admin(self, actor: str) -> bool:
        return actor == "owner" or actor in self.admin_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "Budget", "ResourceConfig",
    "ResourceError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
