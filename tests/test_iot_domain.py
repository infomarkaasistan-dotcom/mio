"""MIO Core · IoT Domain (Faz 4 · Domain 34) — üretim testleri: unit+integration+smoke.

Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik connector üzerinden. Telemetri alım +
eşik-tabanlı uyarı (deterministik), aktüatör komutları + Madde 24 onay kapısı, sensör-komut invariantı,
connector routing, DÜRÜST no_connector, authorization, events doğrulanır."""

import pytest

from mio_core.domains.iot import (
    IoTDomain,
    IoTEvents,
    IoTRepository,
    NotFoundError,
    OpStatus,
    Protocol,
    Risk,
    ThingKind,
    UnauthorizedError,
    ValidationError,
    classify_risk,
)
from mio_core.events import EventBus


def _build():
    repo = IoTRepository(":memory:")
    bus = EventBus(record=True)
    dom = IoTDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def io():
    return _build()


# ---- UNIT: risk sınıflandırma + validation + authz ----
def test_risk_and_authz(io):
    d, _r, _b = io
    assert classify_risk("read temperature") == Risk.LOW
    assert classify_risk("unlock door") == Risk.HIGH          # tehlikeli aktüatör işareti
    assert classify_risk("set", declared=Risk.HIGH) == Risk.HIGH
    with pytest.raises(UnauthorizedError):
        d.register_thing("Reasoning", "Termometre")           # reader ama writer değil
    with pytest.raises(ValidationError):
        d.register_thing("owner", "X", kind="uydurma")
    with pytest.raises(ValidationError):
        d.register_thing("owner", "X", protocol="uydurma")


# ---- INTEGRATION: telemetri alım + deterministik eşik-uyarı ----
def test_telemetry_ingest_and_threshold_alert(io):
    d, _r, bus = io
    sensor = d.register_thing("owner", "Kazan Sıcaklık", kind=ThingKind.SENSOR, protocol=Protocol.MQTT)
    d.add_alert_rule("owner", sensor["id"], "temp", ">", 80.0)
    r1 = d.ingest("owner", sensor["id"], "temp", 55.0, unit="C")
    assert r1["alerts"] == []                                  # eşik altı → alarm yok
    r2 = d.ingest("owner", sensor["id"], "temp", 95.5, unit="C")
    assert len(r2["alerts"]) == 1 and r2["alerts"][0]["threshold"] == 80.0   # eşik aşıldı → alarm
    assert any(e["type"] == IoTEvents.ALERT_TRIGGERED for e in bus.history())
    # latest + readings + alerts sorguları
    assert d.latest("owner", sensor["id"], "temp")["value"] == 95.5
    assert len(d.readings("owner", sensor["id"], metric="temp")) == 2
    assert len(d.alerts("owner", thing_id=sensor["id"])) == 1
    with pytest.raises(ValidationError):
        d.ingest("owner", sensor["id"], "temp", "sayı-değil")  # sayısal olmayan reddedilir


# ---- INTEGRATION: sensör komut kabul etmez (invariant) ----
def test_sensor_rejects_command(io):
    d, _r, _b = io
    sensor = d.register_thing("owner", "Nem", kind=ThingKind.SENSOR)
    with pytest.raises(ValidationError):
        d.send_command("owner", sensor["id"], "turn on")


# ---- INTEGRATION: yüksek-risk aktüatör komut → requires_approval (Madde 24) ----
def test_high_risk_actuator_requires_approval(io):
    d, _r, bus = io
    valve = d.register_thing("owner", "Ana Vana", kind=ThingKind.ACTUATOR, protocol=Protocol.MQTT)
    d.register_connector(Protocol.MQTT, lambda ctx: {"applied": ctx["command"]}, name="mqtt-adapter")
    # düşük risk → çalışır
    ok = d.send_command("owner", valve["id"], "set flow 5")
    assert ok["status"] == OpStatus.COMPLETED
    # yüksek risk (open valve → geri-alınamaz) + onaysız → requires_approval
    danger = d.send_command("Operations", valve["id"], "open valve fully")
    assert danger["status"] == OpStatus.REQUIRES_APPROVAL and danger["risk"] == Risk.HIGH
    assert any(e["type"] == IoTEvents.APPROVAL_REQUIRED for e in bus.history())
    with pytest.raises(UnauthorizedError):
        d.approve_command("Operations", danger["id"])         # Operations approver DEĞİL
    approved = d.approve_command("owner", danger["id"])        # owner onaylar → çalışır
    assert approved["status"] == OpStatus.COMPLETED and approved["approved_by"] == "owner"
    assert any(e["type"] == IoTEvents.APPROVED for e in bus.history())


def test_high_risk_preapproval_runs(io):
    d, _r, _b = io
    lock = d.register_thing("owner", "Kapı Kilidi", kind=ThingKind.ACTUATOR, protocol=Protocol.ZIGBEE)
    d.register_connector(Protocol.ZIGBEE, lambda ctx: {"ok": True})
    job = d.send_command("owner", lock["id"], "unlock door", user_approved=True)   # önceden onaylı
    assert job["status"] == OpStatus.COMPLETED


# ---- INTEGRATION: connector YOK → DÜRÜST no_connector ----
def test_no_connector_is_honest(io):
    d, _r, bus = io
    relay = d.register_thing("owner", "Röle", kind=ThingKind.ACTUATOR, protocol=Protocol.COAP)
    job = d.send_command("owner", relay["id"], "toggle")
    assert job["status"] == OpStatus.NO_CONNECTOR and job["result"] == {}
    with pytest.raises(NotFoundError):
        d.send_command("owner", "yok-thing", "x")
    assert any(e["type"] == IoTEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: connector hatası → failed ----
def test_connector_failure_becomes_failed(io):
    d, _r, _b = io
    gw = d.register_thing("owner", "Gateway", kind=ThingKind.GATEWAY, protocol=Protocol.HTTP)
    d.register_connector(Protocol.HTTP, lambda ctx: (_ for _ in ()).throw(RuntimeError("broker down")))
    job = d.send_command("owner", gw["id"], "sync")
    assert job["status"] == OpStatus.FAILED and "broker down" in job["error"]


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(io):
    d, _r, _b = io
    s = d.register_thing("owner", "S", kind=ThingKind.SENSOR)
    d.ingest("owner", s["id"], "temp", 10.0)
    a = d.register_thing("owner", "A", kind=ThingKind.ACTUATOR)
    d.send_command("owner", a["id"], "reset device")          # high → requires_approval
    st = d.stats()
    assert st["things"] == 2 and st["readings"] == 1 and st["pending_approval"] == 1
    assert st["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "iot" and "send_command" in c["operations"] and "approve_command" in c["operations"]
    assert len(d.list_things("owner")) == 2


# ---- SMOKE: boot() → Madde 24 + no_connector uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    sensor = mio.iot.register_thing("owner", "Saha Sensörü", kind=ThingKind.SENSOR, protocol=Protocol.MQTT)
    mio.iot.add_alert_rule("owner", sensor["id"], "co2", ">=", 1000.0)
    fired = mio.iot.ingest("owner", sensor["id"], "co2", 1200.0)
    assert len(fired["alerts"]) == 1                          # deterministik eşik uyarısı çalışır
    valve = mio.iot.register_thing("owner", "Vana", kind=ThingKind.ACTUATOR, protocol=Protocol.MQTT)
    danger = mio.iot.send_command("owner", valve["id"], "shutdown pump")
    assert danger["status"] == OpStatus.REQUIRES_APPROVAL     # Madde 24: onaysız çalışmaz
    approved = mio.iot.approve_command("owner", danger["id"])  # connector yok → dürüst no_connector
    assert approved["status"] == OpStatus.NO_CONNECTOR
    assert mio.iot.contract()["version"] == "1.0.0"
    mio.close()
