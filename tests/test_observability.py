"""MIO Core · Observability (Production Hardening #4) — structured logging + tracing + birleşik metrics KANITI.

İddia değil doğrulama: JSON structured log + sır maskeleme, deterministik nested tracing (trace_id correlation +
parent nesting + süre + hata durumu), ve tüm domainleri toplayan mio.metrics(). Deterministik; stdlib-only."""

import io
import json
import logging

import pytest

from mio_core.platform.observability import (
    SENSITIVE_KEY_MARKERS,
    StructuredFormatter,
    Tracer,
    redact_mapping,
)


# ---- structured logging (JSON) + sır maskeleme ----
def test_structured_formatter_emits_json_with_fields():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(StructuredFormatter(service="mio-test"))
    logger = logging.getLogger("mio.test.structured")
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]
    logger.propagate = False

    logger.info("domain executed", extra={"domain": "iot", "op": "ingest", "count": 3})
    rec = json.loads(buf.getvalue().strip())
    assert rec["level"] == "INFO" and rec["service"] == "mio-test"
    assert rec["message"] == "domain executed"
    assert rec["domain"] == "iot" and rec["op"] == "ingest" and rec["count"] == 3
    assert "ts" in rec and rec["logger"] == "mio.test.structured"


def test_structured_formatter_redacts_secrets():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(StructuredFormatter())
    logger = logging.getLogger("mio.test.redact")
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]
    logger.propagate = False

    logger.info("auth", extra={"api_key": "sk-REAL-SECRET", "user": "owner"})
    rec = json.loads(buf.getvalue().strip())
    assert rec["api_key"] == "***redacted***"      # sır maskelendi (asla sızmaz)
    assert rec["user"] == "owner"                  # sır olmayan korunur


def test_redact_mapping_nested_and_markers():
    data = {"token": "abc", "nested": {"password": "x", "ok": 1}, "plain": "v"}
    out = redact_mapping(data)
    assert out["token"] == "***redacted***"
    assert out["nested"]["password"] == "***redacted***" and out["nested"]["ok"] == 1
    assert out["plain"] == "v"
    assert "key" in SENSITIVE_KEY_MARKERS and "secret" in SENSITIVE_KEY_MARKERS


# ---- deterministik tracing ----
def _det_tracer():
    """Sayaç-clock + sıralı id → tam deterministik tracer (test)."""
    ticks = iter(range(0, 100000))
    ids = iter(f"id{i}" for i in range(1000))
    return Tracer(clock=lambda: float(next(ticks)), id_factory=lambda: next(ids))


def test_tracer_nested_spans_share_trace_and_parent():
    t = _det_tracer()
    with t.span("root", domain="executive"):
        with t.span("child", domain="iot"):
            pass
    spans = {s["name"]: s for s in t.spans()}
    root, child = spans["root"], spans["child"]
    # correlation: aynı trace_id
    assert root["trace_id"] == child["trace_id"]
    # nesting: child'ın parent'ı root
    assert child["parent_id"] == root["span_id"] and root["parent_id"] is None
    # süre deterministik (clock sayaç) ve pozitif
    assert root["duration"] is not None and child["duration"] is not None
    assert root["status"] == "ok" and child["status"] == "ok"
    assert child["tags"]["domain"] == "iot"


def test_tracer_marks_error_and_reraises():
    t = _det_tracer()
    with pytest.raises(RuntimeError):
        with t.span("failing"):
            raise RuntimeError("çöktü")
    sp = t.spans()[0]
    assert sp["status"] == "error" and "çöktü" in sp["tags"]["error"]


def test_tracer_trace_correlation_view():
    t = _det_tracer()
    with t.span("a"):
        with t.span("b"):
            pass
    tid = t.spans()[0]["trace_id"]
    correlated = t.trace(tid)
    assert len(correlated) == 2 and all(s["trace_id"] == tid for s in correlated)


# ---- birleşik metrics toplayıcı (runtime) ----
def test_runtime_metrics_aggregates_all_domains(tmp_path):
    from mio_core.runtime import boot, _READINESS_DOMAINS
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        m = mio.metrics()
        assert m["domain_count"] == len(_READINESS_DOMAINS)
        # her domain stats'ı sözleşme versiyonu içerir
        assert m["domains"]["iot"]["contract_version"] == "1.0.0"
        assert m["domains"]["extension_sdk"]["contract_version"] == "1.0.0"
        assert "event_bus" in m and m["closed"] is False
        # bir işlem sonrası metrik yansır (deterministik snapshot)
        mio.multi_agent.register_agent("owner", "a", capabilities=["x"])
        assert mio.metrics()["domains"]["multi_agent"]["agents"] == 1
    finally:
        mio.close()
