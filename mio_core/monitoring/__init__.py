"""MIO Core · Monitoring Adapter Layer. Çekirdek metrik ÜRETİR; adapter dış sistemlere AKTARIR.

Executive → Metrics/Tracer → MonitoringAdapter → [Prometheus (scrape/push) · OpenTelemetry (OTLP/HTTP-JSON)].
Çekirdek hiçbir gözlemleme framework'üne bağımlı DEĞİL (stdlib-only)."""

from .adapter import MonitoringAdapter
from .formats import flatten_samples, render_prometheus, to_otlp_metrics

__all__ = ["MonitoringAdapter", "render_prometheus", "to_otlp_metrics", "flatten_samples"]
