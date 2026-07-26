"""MIO Core · Observability Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Sistemin canlı telemetri resmini toplar: EventBus'ı dinler (subscribe_all), olay-tipi sayaçları + özel
metrikler tutar, deterministik SAĞLIK roll-up'ı üretir. Çekirdeğe dokunmaz (gövde/observability bileşeni)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HealthStatus:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class MetricKind:
    COUNTER = "counter"
    GAUGE = "gauge"
    ALL = {COUNTER, GAUGE}


EVENT_PREFIX = "evt:"          # olay-tipi sayaçları bu önekle saklanır (özel metriklerden ayrık)


class ObservabilityError(Exception):
    """Observability Domain temel hatası."""


class ValidationError(ObservabilityError):
    pass


class UnauthorizedError(ObservabilityError):
    pass


@dataclass
class TelemetryEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: uuid4().hex[:16])

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "data": self.data, "at": self.at}


@dataclass
class ObservabilityConfig:
    max_events: int = 1000               # telemetri olay halkası kapasitesi
    prune_every: int = 100               # her N olayda bir eski kayıtları buda
    # Sağlık eşikleri (dürüst: governance blokları SAĞLIKLI davranıştır → dahil edilmez)
    degraded_disabled_jobs: int = 1      # LoopGuard bir devre açtı → degraded
    unhealthy_disabled_jobs: int = 3
    degraded_zombies: int = 1            # önceki çökme tespit edildi → degraded
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Workflow", "Communication"})
    writer_actors: set = field(default_factory=lambda: {"owner", "Executive", "Operations", "Workflow"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "HealthStatus", "MetricKind", "EVENT_PREFIX", "TelemetryEvent", "ObservabilityConfig",
    "ObservabilityError", "ValidationError", "UnauthorizedError",
]
