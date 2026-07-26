"""MIO Core · Observability Domain (Faz 4 · Domain 13) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek EventBus + SQLite telemetri deposu üzerinden. Pasif olay dinleme/sayma, özel
metrikler, deterministik sağlık roll-up (governance blokları sağlıklı sayılır), authorization, süreklilik ve
uçtan-uca akış (tüm domainleri kapsama) doğrulanır."""

import pytest

from mio_core.domains.observability import (
    HealthStatus,
    MetricKind,
    ObservabilityDomain,
    ObsEvents,
    TelemetryRepository,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = TelemetryRepository(":memory:")
    bus = EventBus(record=True)
    dom = ObservabilityDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def obs():
    return _build()


# ---- INTEGRATION: pasif olay dinleme + sayma ----
def test_counts_bus_events(obs):
    d, _r, bus = obs
    bus.publish("execution.blocked", {"x": 1})
    bus.publish("execution.blocked", {"x": 2})
    bus.publish("scheduler.tick", {"clock": 1})
    snap = d.snapshot("owner")
    assert snap["events"]["execution.blocked"] == 2
    assert snap["events"]["scheduler.tick"] == 1
    assert snap["total_events"] >= 3


# ---- UNIT: özel metrik + validation ----
def test_record_metric_and_incr(obs):
    d, _r, _b = obs
    d.record_metric("owner", "revenue_forecast", 5000, kind=MetricKind.GAUGE)
    d.incr("owner", "api_calls")
    d.incr("owner", "api_calls", by=4)
    snap = d.snapshot("owner")
    assert snap["metrics"]["revenue_forecast"] == 5000 and snap["metrics"]["api_calls"] == 5
    with pytest.raises(ValidationError):
        d.record_metric("owner", "  ", 1)
    with pytest.raises(ValidationError):
        d.record_metric("owner", "evt:hile", 1)              # ayrılmış önek
    with pytest.raises(ValidationError):
        d.record_metric("owner", "x", 1, kind="uydurma")


# ---- UNIT: authorization ----
def test_authorization(obs):
    d, _r, _b = obs
    with pytest.raises(UnauthorizedError):
        d.record_metric("yabanci", "x", 1)
    with pytest.raises(UnauthorizedError):
        d.snapshot("yabanci")


# ---- INTEGRATION: deterministik sağlık ----
def test_health_healthy_by_default(obs):
    d, _r, bus = obs
    bus.publish("execution.blocked", {})                     # governance bloğu → SAĞLIKLI
    bus.publish("vertical.guardrail_gated", {})              # guardrail → SAĞLIKLI
    h = d.health("owner")
    assert h["status"] == HealthStatus.HEALTHY
    assert h["signals"]["governance_blocks"] == 1


def test_health_degraded_on_disabled_job(obs):
    d, _r, bus = obs
    bus.publish("scheduler.job_disabled", {"job": "x"})      # LoopGuard devre açtı → degraded
    assert d.health("owner")["status"] == HealthStatus.DEGRADED
    assert any(e["type"] == ObsEvents.HEALTH_EVALUATED for e in bus.history())


def test_health_unhealthy_on_repeated_disable(obs):
    d, _r, bus = obs
    for _ in range(3):
        bus.publish("scheduler.job_disabled", {})
    assert d.health("owner")["status"] == HealthStatus.UNHEALTHY


# ---- INTEGRATION: süreklilik (metrikler kalıcı) ----
def test_metric_persistence_across_restart():
    repo = TelemetryRepository(":memory:")
    d1 = ObservabilityDomain(repo)                            # bus yok
    d1.record_metric("owner", "counter_a", 7)
    d2 = ObservabilityDomain(repo)                            # aynı repo → geri yükler
    assert d2.snapshot("owner")["metrics"]["counter_a"] == 7


# ---- INTEGRATION: events + stats + contract ----
def test_events_stats_contract(obs):
    d, _r, bus = obs
    bus.publish("communication.replied", {"source": "handler"})
    evs = d.events("owner", type="communication.replied")
    assert evs and evs[0]["type"] == "communication.replied"
    s = d.stats()
    assert s["events_seen"] >= 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "observability" and "health" in c["operations"]


# ---- SMOKE: boot() → tüm domainleri kapsayan telemetri ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    # canlı domain operasyonları → observability otomatik sayar (event-driven)
    mio.communication.converse("owner", "merhaba")
    mio.scheduler.tick("owner")
    snap = mio.observability_domain.snapshot("owner")
    assert snap["events"].get("communication.replied", 0) >= 1
    assert snap["events"].get("scheduler.tick", 0) >= 1
    assert mio.observability_domain.health("owner")["status"] == HealthStatus.HEALTHY
    assert mio.observability_domain.contract()["version"] == "1.0.0"
    mio.close()
