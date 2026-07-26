"""MIO Core · Monitoring Adapter (Interface Katmanı #4) — çekirdek metrik → Prometheus/OTLP KANITI.

Çekirdek yalnız metrik üretir; adapter dış formatlara çevirir + push eder. Framework bağımlılığı YOK (stdlib).
Deterministik; push transport enjekte edilebilir (ağ yok). Prometheus text, OTLP/HTTP-JSON, Pushgateway PUT,
OTLP export, görünür hata (Madde 27), CLI+HTTP paylaşımı doğrulanır."""

import json

import pytest

from mio_core.monitoring import MonitoringAdapter, flatten_samples, render_prometheus, to_otlp_metrics


_METRICS = {
    "domain_count": 2,
    "closed": False,
    "domains": {"iot": {"readings": 5, "things": 1, "contract_version": "1.0.0"},
                "multi_agent": {"agents": 3}},
    "connectors": {"connectors": 1, "executed": 4, "by_category": {"ai": 1, "system": 0}},
    "event_bus": {"subscriber_errors": {"total": 0}},
}
_READY = {"ready": True, "checks": {"domains": {"ready": 24, "total": 24}}}


# ---- format: flatten + prometheus ----
def test_flatten_samples_numeric_only():
    samples = flatten_samples(_METRICS, readiness=_READY)
    names = {n for n, _l, _v in samples}
    assert "mio_domain_count" in names and "mio_up" in names and "mio_ready" in names
    # contract_version (sayısal değil) dışlanır
    assert all(not (n == "mio_domain_stat" and lb.get("stat") == "contract_version")
               for n, lb, _v in samples)
    # etiketli domain stat mevcut
    assert ("mio_domain_stat", {"domain": "iot", "stat": "readings"}, 5) in samples


def test_render_prometheus_format():
    text = render_prometheus(_METRICS, readiness=_READY)
    lines = text.splitlines()
    assert "mio_domain_count 24" not in lines               # gerçek değer 2
    assert "mio_domain_count 2" in lines
    assert "mio_up 1" in lines and "mio_ready 1" in lines
    assert 'mio_domain_stat{domain="iot",stat="readings"} 5' in lines
    assert 'mio_connector_by_category{category="ai"} 1' in lines
    # her metrik için HELP + TYPE var
    assert "# TYPE mio_up gauge" in lines and "# HELP mio_domain_count MIO Executive OS metric" in lines


def test_prometheus_escapes_labels():
    m = {"domain_count": 0, "domains": {'a"b': {"x": 1}}}
    text = render_prometheus(m)
    assert 'domain="a\\"b"' in text                          # tırnak kaçışlı


# ---- format: OTLP/HTTP-JSON ----
def test_to_otlp_metrics_structure():
    o = to_otlp_metrics(_METRICS, readiness=_READY, now_ns=1234567890)
    rm = o["resourceMetrics"][0]
    assert rm["resource"]["attributes"][0]["value"]["stringValue"] == "mio-executive-os"
    metrics = rm["scopeMetrics"][0]["metrics"]
    by_name = {m["name"]: m for m in metrics}
    dp = by_name["mio_domain_count"]["gauge"]["dataPoints"][0]
    assert dp["asInt"] == "2" and dp["timeUnixNano"] == "1234567890"
    # etiketli metrik OTLP attributes'a çevrilir
    stat = by_name["mio_domain_stat"]["gauge"]["dataPoints"]
    assert any(a["value"]["stringValue"] == "iot"
               for d in stat for a in d.get("attributes", []))


# ---- adapter: kaynak okuma + export ----
def _adapter():
    return MonitoringAdapter(lambda: dict(_METRICS), readiness_fn=lambda: dict(_READY))


def test_adapter_prometheus_and_snapshot():
    a = _adapter()
    assert "mio_up 1" in a.prometheus()
    snap = a.snapshot()
    assert snap["metrics"]["domain_count"] == 2 and snap["readiness"]["ready"] is True


def test_push_to_pushgateway_injected_transport():
    a = _adapter()
    captured = {}

    class _Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *x): return False

    def fake_urlopen(req, timeout=10):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = req.data.decode("utf-8")
        return _Resp()

    r = a.push_to_pushgateway("http://pg:9091", "mio", instance="node1", urlopen=fake_urlopen)
    assert r["ok"] and r["status"] == 200
    assert captured["method"] == "PUT"
    assert captured["url"] == "http://pg:9091/metrics/job/mio/instance/node1"
    assert "mio_up 1" in captured["body"]                    # gönderilen gövde Prometheus text


def test_export_otlp_injected_transport():
    a = _adapter()
    captured = {}

    class _Resp:
        status = 202
        def __enter__(self): return self
        def __exit__(self, *x): return False

    def fake_urlopen(req, timeout=10):
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    r = a.export_otlp("http://otelcol:4318", urlopen=fake_urlopen)
    assert r["ok"] and captured["url"] == "http://otelcol:4318/v1/metrics"
    assert "resourceMetrics" in captured["payload"]


def test_export_failure_is_visible_not_crash():
    a = _adapter()
    def boom(req, timeout=10):
        raise OSError("collector unreachable")
    r = a.push_to_pushgateway("http://pg:9091", "mio", urlopen=boom)
    assert r["ok"] is False and "collector unreachable" in r["error"]   # görünür (Madde 27), çökmez


# ---- entegrasyon: boot + appservice + CLI/HTTP paylaşımı ----
def test_via_runtime_and_shared_surface(tmp_path):
    from mio_core.runtime import boot
    from mio_core import appservice
    from mio_core.cli import run_command
    from mio_core.http_api import route_request
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        assert "mio_up 1" in mio.monitoring.prometheus()
        # appservice (CLI+HTTP ortak)
        assert "mio_domain_count" in appservice.prometheus_metrics(mio)
        # CLI prometheus komutu → text
        code, out = run_command(mio, ["prometheus"])
        assert code == 0 and "mio_up 1" in out
        # HTTP GET /metrics/prometheus → text (route_request str döner, 200)
        st, data = route_request(mio, "GET", "/metrics/prometheus", {}, None)
        assert st == 200 and isinstance(data, str) and "mio_up 1" in data
        # HTTP GET /metrics/otlp → OTLP dict
        st2, data2 = route_request(mio, "GET", "/metrics/otlp", {}, None)
        assert st2 == 200 and "resourceMetrics" in data2
    finally:
        mio.close()
