# Monitoring — Adapter Layer (Interface Katmanı #4)

> **Çekirdek yalnız metrik ÜRETİR** (`mio.metrics()` · `readiness()` · StructuredFormatter · Tracer). **Monitoring
> Adapter** bunları dış sistemlere AKTARIR. Çekirdek hiçbir gözlemleme framework'üne (prometheus_client /
> opentelemetry SDK) **bağımlı DEĞİL** — adapter stdlib-only (json + urllib).

```
Executive → Metrics / Tracer → Monitoring Adapter → [ Prometheus · OpenTelemetry (OTLP) ]
```

## Prometheus (scrape — en yaygın)
```bash
python -m mio_core serve                 # HTTP adapter
curl localhost:8080/metrics/prometheus   # text/plain; version=0.0.4  → Prometheus doğrudan scrape eder
python -m mio_core prometheus            # CLI'dan da alınır (debug)
```
`prometheus.yml`:
```yaml
scrape_configs:
  - job_name: mio
    metrics_path: /metrics/prometheus
    static_configs: [{ targets: ["mio-host:8080"] }]
```
Örnek metrikler: `mio_up`, `mio_domain_count`, `mio_ready`, `mio_domain_stat{domain,stat}`,
`mio_connector_stat{stat}`, `mio_connector_by_category{category}`, `mio_event_subscriber_errors`.

## Prometheus Pushgateway (batch/kısa-ömürlü işler)
```python
mio.monitoring.push_to_pushgateway("http://pushgateway:9091", job="mio", instance="node1")
# PUT {gateway}/metrics/job/mio/instance/node1  (Content-Type: text/plain; version=0.0.4)
```

## OpenTelemetry (OTLP/HTTP-JSON)
```bash
curl localhost:8080/metrics/otlp          # OTLP resourceMetrics/scopeMetrics/gauge (JSON)
```
```python
mio.monitoring.export_otlp("http://otel-collector:4318")   # POST {endpoint}/v1/metrics (OTLP/HTTP JSON)
```
OTLP/HTTP **JSON** kodlaması spec-uyumludur; otelcol doğrudan kabul eder. Push transport enjekte edilebilir
(deterministik test); dış sistem hatası **görünür** olur (`{ok:false, error}` — Madde 27), süreç çökmez.

## Structured logging & tracing (mevcut, çekirdekte)
- `mio_core/platform/observability.StructuredFormatter` → tek-satır JSON log; sır anahtarları otomatik maskelenir.
- `mio_core/platform/observability.Tracer` → nested span + `trace_id` correlation; MonitoringAdapter'a `tracer`
  verilirse `snapshot()["spans"]` ile dışa aktarılır.

## Kapsam / dürüstlük
**TAM çalışır:** Prometheus text-exposition (scrape) + Pushgateway PUT + OTLP/HTTP-JSON metrics export. **Ayrı
adapter paketi (gelecek, çekirdeğe bağımlılık eklemeden):** full OTLP-protobuf + OpenTelemetry SDK (auto-
instrumentation / batching / retry / trace export), tıpkı FastAPI/Flask gibi. Test: `tests/test_monitoring.py` (9).
