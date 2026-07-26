"""MIO Core · Monitoring Adapter — çekirdek metriklerini dış sistemlere AKTARIR, stdlib-only.

Executive → Metrics/Tracer → **Monitoring Adapter** → [Prometheus · OpenTelemetry]. Çekirdek gözlemleme
framework'üne BAĞLI DEĞİL; bu adapter köprüdür. Metrik kaynağı enjekte edilir (callable) → runtime'a sıkı bağlı
değil, test edilebilir. Push için stdlib `urllib` (enjekte edilebilir → deterministik test).

Kapsam (dürüst): Prometheus text-exposition (scrape) + Pushgateway push + OTLP/HTTP-JSON metrics export TAM
çalışır. Full OTLP-protobuf + OpenTelemetry SDK (auto-instrumentation/batching) AYRI adapter paketidir (çekirdeğe
bağımlılık eklemez)."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Optional

from .formats import render_prometheus, to_otlp_metrics


class MonitoringAdapter:
    def __init__(self, metrics_fn: Callable[[], dict], *,
                 readiness_fn: Optional[Callable[[], dict]] = None,
                 tracer=None, service: str = "mio-executive-os") -> None:
        self._metrics_fn = metrics_fn
        self._readiness_fn = readiness_fn
        self._tracer = tracer
        self._service = service

    # -- kaynak okuma -- #
    def _readiness(self) -> Optional[dict]:
        return self._readiness_fn() if self._readiness_fn is not None else None

    def snapshot(self) -> dict[str, Any]:
        """Ham JSON snapshot (metrics + readiness + trace span sayısı)."""
        snap: dict[str, Any] = {"metrics": self._metrics_fn()}
        if self._readiness_fn is not None:
            snap["readiness"] = self._readiness_fn()
        if self._tracer is not None:
            snap["spans"] = self._tracer.spans()
        return snap

    # -- Prometheus -- #
    def prometheus(self) -> str:
        """Prometheus text exposition — scrape endpoint (`GET /metrics/prometheus`) için."""
        return render_prometheus(self._metrics_fn(), readiness=self._readiness())

    def push_to_pushgateway(self, gateway_url: str, job: str, *, instance: Optional[str] = None,
                            urlopen: Optional[Callable] = None) -> dict[str, Any]:
        """Prometheus Pushgateway'e PUT (batch/kısa-ömürlü işler için). urlopen enjekte edilebilir (test)."""
        opener = urlopen or urllib.request.urlopen
        path = f"{gateway_url.rstrip('/')}/metrics/job/{job}"
        if instance:
            path += f"/instance/{instance}"
        req = urllib.request.Request(path, data=self.prometheus().encode("utf-8"), method="PUT",
                                     headers={"Content-Type": "text/plain; version=0.0.4"})
        return self._send(opener, req, path)

    # -- OpenTelemetry (OTLP/HTTP JSON) -- #
    def otlp_metrics(self) -> dict[str, Any]:
        return to_otlp_metrics(self._metrics_fn(), service=self._service, readiness=self._readiness())

    def export_otlp(self, endpoint: str, *, urlopen: Optional[Callable] = None,
                    headers: Optional[dict] = None) -> dict[str, Any]:
        """OTLP/HTTP-JSON metrics → `POST {endpoint}/v1/metrics`. Collector (otelcol) doğrudan kabul eder."""
        opener = urlopen or urllib.request.urlopen
        url = f"{endpoint.rstrip('/')}/v1/metrics"
        payload = json.dumps(self.otlp_metrics(), ensure_ascii=False).encode("utf-8")
        hdrs = {"Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(url, data=payload, method="POST", headers=hdrs)
        return self._send(opener, req, url)

    # -- generic JSON push (herhangi bir collector) -- #
    def export_json(self, url: str, *, urlopen: Optional[Callable] = None) -> dict[str, Any]:
        opener = urlopen or urllib.request.urlopen
        payload = json.dumps(self.snapshot(), ensure_ascii=False, default=str).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        return self._send(opener, req, url)

    @staticmethod
    def _send(opener: Callable, req, url: str) -> dict[str, Any]:
        try:
            with opener(req, timeout=10) as resp:
                status = getattr(resp, "status", 0) or 0
                return {"ok": 200 <= status < 300, "status": status, "url": url}
        except Exception as exc:  # noqa: BLE001 — dış sistem hatası GÖRÜNÜR olur (Madde 27), çökmez
            return {"ok": False, "status": 0, "url": url, "error": str(exc)[:200]}


__all__ = ["MonitoringAdapter"]
