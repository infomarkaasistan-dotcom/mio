"""MIO Core · Capability Adapter Layer (Connector) — üretim testleri: registry+manager+advisor+entegrasyon.

Anayasa özü: Executive isimle değil CAPABILITY ile çağırır; connector yoksa ÇÖKMEZ (connector_unavailable);
AI DANIŞMAN (karar vermez); yüksek-risk ONAY ister (Madde 24); sağlayıcı hatası → FAILOVER. Deterministik dispatch
(priority+health). Placeholder YOK; enjekte edilen fake connector'larla."""

import pytest

from mio_core.connectors import (
    Advisor,
    Cap,
    CallableConnector,
    ConnectorCategory,
    ConnectorEvents,
    ConnectorManager,
    ConnectorRegistry,
    Outcome,
    ValidationError,
)
from mio_core.events import EventBus


def _mgr():
    reg = ConnectorRegistry()
    bus = EventBus(record=True)
    return ConnectorManager(reg, bus=bus), reg, bus


def _conn(name, category, caps, priority=100, health=None):
    return CallableConnector(name, category, handlers=caps, priority=priority, health_fn=health)


# ---- UNIT: registry ----
def test_registry_validation_and_priority():
    reg = ConnectorRegistry()
    with pytest.raises(ValidationError):
        CallableConnector("x", "uydurma", handlers={"a": lambda r: 1})   # geçersiz kategori
    with pytest.raises(ValidationError):
        CallableConnector("x", ConnectorCategory.AI, handlers={})        # capability yok
    lo = _conn("smtp", ConnectorCategory.COMMUNICATION, {Cap.SEND_EMAIL: lambda r: 1}, priority=50)
    hi = _conn("gmail", ConnectorCategory.COMMUNICATION, {Cap.SEND_EMAIL: lambda r: 2}, priority=100)
    reg.register(lo); reg.register(hi)
    # capability ile sorgu → öncelik sırası (yüksek önce)
    order = [c.name for c in reg.providers_for(Cap.SEND_EMAIL)]
    assert order == ["gmail", "smtp"]
    assert reg.has_capability(Cap.SEND_EMAIL) and not reg.has_capability("yok")
    assert reg.capabilities()[Cap.SEND_EMAIL] == ["gmail", "smtp"]
    assert reg.stats()["by_category"]["communication"] == 2


# ---- INTEGRATION: connector YOK → connector_unavailable (çökmez) ----
def test_unavailable_does_not_crash():
    m, _r, bus = _mgr()
    r = m.execute("send_email", {"to": "a@b.com"})
    assert r["ok"] is False and r["status"] == Outcome.CONNECTOR_UNAVAILABLE
    assert "not configured" in r["message"]
    assert any(e["type"] == ConnectorEvents.UNAVAILABLE for e in bus.history())
    assert m.available("send_email") is False


# ---- INTEGRATION: capability ile dispatch (isimle değil) + öncelik ----
def test_capability_dispatch_by_priority():
    m, _r, bus = _mgr()
    m.register(_conn("smtp", ConnectorCategory.COMMUNICATION, {Cap.SEND_EMAIL: lambda r: {"via": "smtp"}}, 50))
    m.register(_conn("gmail", ConnectorCategory.COMMUNICATION, {Cap.SEND_EMAIL: lambda r: {"via": "gmail"}}, 100))
    r = m.execute("send_email", {"to": "x@y.com"})
    assert r["ok"] and r["status"] == Outcome.EXECUTED and r["connector"] == "gmail"   # yüksek öncelik
    assert r["result"] == {"via": "gmail"}
    assert any(e["type"] == ConnectorEvents.EXECUTED for e in bus.history())


# ---- INTEGRATION: sağlayıcı hatası → FAILOVER (Madde 28) ----
def test_failover_to_next_provider():
    m, _r, bus = _mgr()
    m.register(_conn("broken", ConnectorCategory.COMMUNICATION,
                     {Cap.SEND_MESSAGE: lambda r: (_ for _ in ()).throw(RuntimeError("down"))}, 200))
    m.register(_conn("telegram", ConnectorCategory.COMMUNICATION,
                     {Cap.SEND_MESSAGE: lambda r: {"sent": "telegram"}}, 100))
    r = m.execute("send_message", {"text": "hi"})
    assert r["ok"] and r["connector"] == "telegram"        # yüksek-öncelikli patladı → bir sonrakine
    assert any(e["type"] == ConnectorEvents.FAILOVER for e in bus.history())
    # tüm sağlayıcılar patlarsa → failed (yine çökmez)
    m2, _r2, _b2 = _mgr()
    m2.register(_conn("b1", ConnectorCategory.SYSTEM,
                      {Cap.FS_READ: lambda r: (_ for _ in ()).throw(RuntimeError("x"))}))
    assert m2.execute("fs.read", {})["status"] == Outcome.FAILED


# ---- INTEGRATION: sağlıksız connector atlanır ----
def test_unhealthy_provider_skipped():
    m, _r, _b = _mgr()
    m.register(_conn("sick", ConnectorCategory.COMMUNICATION,
                     {Cap.SEND_EMAIL: lambda r: {"via": "sick"}}, priority=200, health=lambda: False))
    m.register(_conn("ok", ConnectorCategory.COMMUNICATION,
                     {Cap.SEND_EMAIL: lambda r: {"via": "ok"}}, priority=100, health=lambda: True))
    r = m.execute("send_email", {})
    assert r["connector"] == "ok"                          # sağlıksız yüksek-öncelikli atlandı


# ---- INTEGRATION: yüksek-risk capability → requires_approval (Madde 24) ----
def test_high_risk_requires_approval():
    m, _r, bus = _mgr()
    m.register(_conn("shell", ConnectorCategory.SYSTEM, {Cap.SHELL_EXEC: lambda r: {"ran": r.get("cmd")}}))
    unappr = m.execute("shell.exec", {"cmd": "ls"})
    assert unappr["status"] == Outcome.REQUIRES_APPROVAL and unappr["ok"] is False
    assert any(e["type"] == ConnectorEvents.REQUIRES_APPROVAL for e in bus.history())
    appr = m.execute("shell.exec", {"cmd": "ls"}, user_approved=True)
    assert appr["ok"] and appr["result"] == {"ran": "ls"}


# ---- INTEGRATION: Advisor — LLM DANIŞMAN (karar vermez), yoksa çökmez ----
def test_advisor_is_advisor_not_decider():
    m, _r, _b = _mgr()
    adv = Advisor(m)
    assert adv.available() is False
    # danışman yokken çökmez → connector_unavailable (Executive deterministik devam eder)
    assert adv.ask("ne yapmalı?")["status"] == Outcome.CONNECTOR_UNAVAILABLE
    m.register(_conn("ollama", ConnectorCategory.AI,
                     {Cap.AI_ADVISE: lambda r: {"advice": "X yap", "for": r["prompt"]}}))
    out = adv.ask("ne yapmalı?")
    assert out["ok"] and out["result"]["advice"] == "X yap"   # tavsiye (karar değil)
    assert adv.available() is True


# ---- INTEGRATION: boot() ile canlı — varsayılan hiçbir connector yok (graceful) ----
def test_via_runtime_graceful_default(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        # varsayılan: connector yok → her capability dürüstçe unavailable, Executive çalışır
        assert mio.connectors.execute("send_email", {})["status"] == Outcome.CONNECTOR_UNAVAILABLE
        assert mio.advisor.available() is False
        assert mio.connectors.contract()["version"] == "1.0.0"
        # metrics connector katmanını içerir
        assert "connectors" in mio.metrics()
        # çalışma-zamanı connector bağlama
        mio.connectors.register(_conn("fs", ConnectorCategory.SYSTEM, {Cap.FS_READ: lambda r: {"data": "x"}}))
        assert mio.connectors.execute("fs.read", {"path": "/a"})["ok"] is True
    finally:
        mio.close()
