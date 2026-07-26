"""MIO Core · Monitoring · format dönüştürücüler — mio.metrics() → Prometheus text / OTLP-HTTP-JSON, stdlib-only.

**Çekirdek yalnız metrik ÜRETİR** (mio.metrics()/readiness()); bu modül onları dış gözlemleme formatlarına çevirir.
Hiçbir gözlemleme framework'üne (prometheus_client / opentelemetry SDK) bağımlılık YOK — yalnız json + string.
Full OTLP-protobuf/SDK istenirse AYRI adapter paketi (çekirdeğe bağımlılık eklemeden)."""

from __future__ import annotations

import time
from typing import Any, Optional

Sample = tuple  # (name: str, labels: dict, value: float)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def flatten_samples(metrics: dict, *, readiness: Optional[dict] = None) -> list:
    """mio.metrics() (+ opsiyonel readiness) → düz sayısal örnekler [(name, labels, value)]."""
    out: list = []
    out.append(("mio_domain_count", {}, int(metrics.get("domain_count", 0))))
    out.append(("mio_up", {}, 0 if metrics.get("closed") else 1))

    for domain, stats in (metrics.get("domains") or {}).items():
        if not isinstance(stats, dict):
            continue
        for stat, value in stats.items():
            if stat == "contract_version":
                continue
            if _is_number(value):
                out.append(("mio_domain_stat", {"domain": domain, "stat": stat}, value))

    conn = metrics.get("connectors") or {}
    for k, v in conn.items():
        if _is_number(v):
            out.append(("mio_connector_stat", {"stat": k}, v))
    for cat, n in (conn.get("by_category") or {}).items():
        if _is_number(n):
            out.append(("mio_connector_by_category", {"category": cat}, n))

    bus = (metrics.get("event_bus") or {}).get("subscriber_errors")
    if isinstance(bus, dict):
        total = bus.get("total")
        if _is_number(total):
            out.append(("mio_event_subscriber_errors", {}, total))

    if readiness is not None:
        out.append(("mio_ready", {}, 1 if readiness.get("ready") else 0))
        dom = (readiness.get("checks") or {}).get("domains") or {}
        if _is_number(dom.get("ready")):
            out.append(("mio_domains_ready", {}, dom["ready"]))
    return out


# --------------------------------------------------------------------------- #
def _fmt_num(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    return repr(float(v))


def _esc_label(v: Any) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_prometheus(metrics: dict, *, readiness: Optional[dict] = None) -> str:
    """Prometheus text exposition (v0.0.4). Aynı isimli örnekler tek HELP/TYPE altında gruplanır."""
    samples = flatten_samples(metrics, readiness=readiness)
    grouped: dict[str, list] = {}
    order: list = []
    for name, labels, value in samples:
        if name not in grouped:
            grouped[name] = []
            order.append(name)
        grouped[name].append((labels, value))
    lines: list = []
    for name in order:
        lines.append(f"# HELP {name} MIO Executive OS metric")
        lines.append(f"# TYPE {name} gauge")
        for labels, value in grouped[name]:
            if labels:
                lbl = "{" + ",".join(f'{k}="{_esc_label(v)}"' for k, v in sorted(labels.items())) + "}"
            else:
                lbl = ""
            lines.append(f"{name}{lbl} {_fmt_num(value)}")
    return "\n".join(lines) + "\n"


def to_otlp_metrics(metrics: dict, *, service: str = "mio-executive-os",
                    readiness: Optional[dict] = None, now_ns: Optional[int] = None) -> dict:
    """OTLP/HTTP-JSON metrics payload (resourceMetrics/scopeMetrics/gauge). `POST {endpoint}/v1/metrics`."""
    now = str(int(now_ns if now_ns is not None else time.time() * 1e9))
    by_name: dict[str, list] = {}
    order: list = []
    for name, labels, value in flatten_samples(metrics, readiness=readiness):
        dp: dict[str, Any] = {"timeUnixNano": now}
        if isinstance(value, float) and not float(value).is_integer():
            dp["asDouble"] = float(value)
        else:
            dp["asInt"] = str(int(value))
        if labels:
            dp["attributes"] = [{"key": k, "value": {"stringValue": str(v)}}
                                for k, v in sorted(labels.items())]
        if name not in by_name:
            by_name[name] = []
            order.append(name)
        by_name[name].append(dp)
    otlp_metrics = [{"name": name, "gauge": {"dataPoints": by_name[name]}} for name in order]
    return {"resourceMetrics": [{
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
        "scopeMetrics": [{"scope": {"name": "mio"}, "metrics": otlp_metrics}],
    }]}


__all__ = ["flatten_samples", "render_prometheus", "to_otlp_metrics"]
