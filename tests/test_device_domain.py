"""MIO Core · Device & Native Integration Domain (Faz 4 · Domain 33) — üretim testleri: unit+integration+smoke.

Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik handler üzerinden. Risk sınıflandırma,
Madde 24 onay kapısı, connector routing, DÜRÜST no_connector, authorization, events doğrulanır."""

import pytest

from mio_core.domains.device import (
    DeviceKind,
    DeviceNativeDomain,
    DeviceEvents,
    DeviceRepository,
    OpStatus,
    Risk,
    classify_risk,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = DeviceRepository(":memory:")
    bus = EventBus(record=True)
    dom = DeviceNativeDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def dv():
    return _build()


# ---- UNIT: risk sınıflandırma + validation + authz ----
def test_risk_classification_and_authz(dv):
    d, _r, _b = dv
    assert classify_risk("list files") == Risk.LOW
    assert classify_risk("delete /data") == Risk.HIGH        # tehlikeli işaret
    assert classify_risk("read", declared=Risk.HIGH) == Risk.HIGH
    with pytest.raises(UnauthorizedError):
        d.register_device("Reasoning", "PC")                 # reader ama writer değil
    with pytest.raises(ValidationError):
        d.register_device("owner", "PC", kind="uydurma")


# ---- INTEGRATION: yüksek-risk komut → requires_approval (Madde 24) ----
def test_high_risk_requires_approval(dv):
    d, _r, bus = dv
    dev = d.register_device("owner", "Sunucu", kind=DeviceKind.OS)
    d.register_handler(DeviceKind.OS, lambda ctx: {"ran": ctx["operation"]}, name="os-adapter")
    # düşük risk → çalışır
    ok = d.execute("owner", dev["id"], "list processes")
    assert ok["status"] == OpStatus.COMPLETED
    # yüksek risk + onaysız → requires_approval (çalışmaz)
    danger = d.execute("Operations", dev["id"], "shutdown now")
    assert danger["status"] == OpStatus.REQUIRES_APPROVAL and danger["risk"] == Risk.HIGH
    assert any(e["type"] == DeviceEvents.APPROVAL_REQUIRED for e in bus.history())
    # Operations approver DEĞİL
    with pytest.raises(UnauthorizedError):
        d.approve_command("Operations", danger["id"])
    approved = d.approve_command("owner", danger["id"])       # owner onaylar → çalışır
    assert approved["status"] == OpStatus.COMPLETED and approved["approved_by"] == "owner"
    assert any(e["type"] == DeviceEvents.APPROVED for e in bus.history())


def test_high_risk_with_preapproval_runs(dv):
    d, _r, _b = dv
    dev = d.register_device("owner", "PC", kind=DeviceKind.FILESYSTEM)
    d.register_handler(DeviceKind.FILESYSTEM, lambda ctx: {"ok": True})
    job = d.execute("owner", dev["id"], "delete temp", user_approved=True)   # önceden onaylı
    assert job["status"] == OpStatus.COMPLETED


# ---- INTEGRATION: connector YOK → DÜRÜST no_connector ----
def test_no_connector_is_honest(dv):
    d, _r, bus = dv
    dev = d.register_device("owner", "Kamera", kind=DeviceKind.PERIPHERAL)
    job = d.execute("owner", dev["id"], "capture")
    assert job["status"] == OpStatus.NO_CONNECTOR and job["result"] == {}
    with pytest.raises(NotFoundError):
        d.execute("owner", "yok-device", "x")
    assert any(e["type"] == DeviceEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: handler hatası → failed ----
def test_handler_failure_becomes_failed(dv):
    d, _r, _b = dv
    dev = d.register_device("owner", "X", kind=DeviceKind.OS)
    d.register_handler(DeviceKind.OS, lambda ctx: (_ for _ in ()).throw(RuntimeError("izin reddedildi")))
    job = d.execute("owner", dev["id"], "read")
    assert job["status"] == OpStatus.FAILED and "izin reddedildi" in job["error"]


# ---- INTEGRATION: list + stats + contract ----
def test_list_stats_contract(dv):
    d, _r, _b = dv
    dev = d.register_device("owner", "X")
    d.execute("owner", dev["id"], "format disk")             # high → requires_approval
    assert len(d.list_devices("owner")) == 1
    assert len(d.list_jobs("owner", status=OpStatus.REQUIRES_APPROVAL)) == 1
    s = d.stats()
    assert s["devices"] == 1 and s["pending_approval"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "device_native" and "approve_command" in c["operations"]


# ---- SMOKE: boot() → Madde 24 uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    dev = mio.device.register_device("owner", "Yerel OS", kind=DeviceKind.OS)
    danger = mio.device.execute("owner", dev["id"], "reboot system")
    assert danger["status"] == OpStatus.REQUIRES_APPROVAL     # Madde 24: onaysız çalışmaz
    # onaylandıktan sonra handler yoksa dürüstçe no_connector
    approved = mio.device.approve_command("owner", danger["id"])
    assert approved["status"] == OpStatus.NO_CONNECTOR
    assert mio.device.contract()["version"] == "1.0.0"
    mio.close()
