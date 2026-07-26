"""MIO Core · Observability Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

EventBus'ı PASİF dinler (subscribe_all): her olay bir olay-tipi sayacını artırır ve telemetri halkasına
yazılır. Özel metrikler (counter/gauge) kaydedilebilir. Sağlık deterministik eşiklerle hesaplanır — dürüst:
governance blokları SAĞLIKLI davranıştır, unhealthy saymaz. authorization · validation · events · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contract import CONTRACT_VERSION, ObsEvents, observability_contract
from .models import (
    EVENT_PREFIX,
    HealthStatus,
    MetricKind,
    ObservabilityConfig,
    TelemetryEvent,
    UnauthorizedError,
    ValidationError,
)
from .repository import TelemetryRepository

logger = logging.getLogger("mio.domain.observability")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ObservabilityDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: TelemetryRepository, *, bus=None,
                 config: Optional[ObservabilityConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or ObservabilityConfig()
        # Kalıcı metrikleri geri yükle (yeniden başlatmada süreklilik)
        self._metrics: dict[str, float] = {n: v for (n, v, _k) in repository.all_metrics()}
        self._kinds: dict[str, str] = {n: k for (n, _v, k) in repository.all_metrics()}
        self._seen = 0
        if bus is not None:
            bus.subscribe_all(self._on_event)      # PASİF dinleyici (canlı akış)

    # ------------------------------------------------------------------ #
    def _on_event(self, event: dict) -> None:
        """Bus abonesi — asla exception sızdırmaz (bus zaten yakalar, yine de güvence)."""
        try:
            etype = event.get("type", "unknown")
            self._bump(f"{EVENT_PREFIX}{etype}", 1.0)
            self._repo.append_event(TelemetryEvent(type=etype, data=dict(event.get("data") or {}),
                                                   at=event.get("at") or _now()))
            self._seen += 1
            if self._seen % self._cfg.prune_every == 0:
                self._repo.prune_events(self._cfg.max_events)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Observability olay işleme atlandı: %s", exc)

    # ------------------------------------------------------------------ #
    def record_metric(self, actor: str, name: str, value: float, *,
                      kind: str = MetricKind.GAUGE) -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require_metric_name(name)
        if kind not in MetricKind.ALL:
            raise ValidationError(f"Geçersiz metrik türü: {kind}")
        self._set(name, float(value), kind)
        self._emit(ObsEvents.METRIC_RECORDED, {"name": name, "value": value, "kind": kind})
        return {"name": name, "value": self._metrics[name], "kind": kind}

    def incr(self, actor: str, name: str, *, by: float = 1.0) -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require_metric_name(name)
        self._bump(name, float(by), kind=MetricKind.COUNTER)
        return {"name": name, "value": self._metrics[name], "kind": MetricKind.COUNTER}

    def snapshot(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        events = {n[len(EVENT_PREFIX):]: v for n, v in self._metrics.items() if n.startswith(EVENT_PREFIX)}
        custom = {n: v for n, v in self._metrics.items() if not n.startswith(EVENT_PREFIX)}
        return {"events": dict(sorted(events.items())), "metrics": dict(sorted(custom.items())),
                "total_events": int(sum(events.values())), "event_types": len(events)}

    def events(self, actor: str, *, type: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
        self._authorize(actor)
        return self._repo.recent_events(min(int(limit), self._cfg.max_events), type=type)

    def health(self, actor: str) -> dict[str, Any]:
        """Deterministik sağlık roll-up'ı (eşik tabanlı). Governance blokları sağlıklıdır (dahil değil)."""
        self._authorize(actor)
        disabled = int(self._ev("scheduler.job_disabled"))
        zombies = int(self._ev("scheduler.zombie_reaped"))
        blocks = int(self._ev("execution.blocked"))          # bilgi amaçlı — sağlıklı davranış
        gated = int(self._ev("vertical.guardrail_gated"))    # bilgi amaçlı — sağlıklı davranış
        if disabled >= self._cfg.unhealthy_disabled_jobs:
            status = HealthStatus.UNHEALTHY
        elif disabled >= self._cfg.degraded_disabled_jobs or zombies >= self._cfg.degraded_zombies:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY
        signals = {"disabled_jobs": disabled, "zombies_reaped": zombies,
                   "governance_blocks": blocks, "guardrail_gated": gated,
                   "total_events": int(sum(v for n, v in self._metrics.items()
                                           if n.startswith(EVENT_PREFIX)))}
        self._emit(ObsEvents.HEALTH_EVALUATED, {"status": status})
        return {"status": status, "signals": signals,
                "note": "governance blokları ve guardrail kapıları SAĞLIKLI davranıştır (dahil edilmez)."}

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"metrics_tracked": len(self._metrics), "events_stored": self._repo.event_count(),
                "events_seen": self._seen, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return observability_contract()

    # ------------------------------------------------------------------ #
    def _ev(self, etype: str) -> float:
        return self._metrics.get(f"{EVENT_PREFIX}{etype}", 0.0)

    def _bump(self, name: str, by: float, *, kind: str = MetricKind.COUNTER) -> None:
        self._metrics[name] = self._metrics.get(name, 0.0) + by
        self._kinds[name] = kind
        self._repo.put_metric(name, self._metrics[name], kind, _now())

    def _set(self, name: str, value: float, kind: str) -> None:
        self._metrics[name] = value
        self._kinds[name] = kind
        self._repo.put_metric(name, value, kind, _now())

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' observability erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' metrik yazma için yetkili değil")

    def _require_metric_name(self, name: str) -> str:
        v = (name or "").strip()
        if not v:
            raise ValidationError("metrik adı boş olamaz")
        if v.startswith(EVENT_PREFIX):
            raise ValidationError(f"'{EVENT_PREFIX}' öneki olay sayaçlarına ayrılmıştır")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
