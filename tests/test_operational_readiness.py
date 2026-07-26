"""MIO Core · Operational Readiness (Production Hardening #1b) — üretim testleri.

Kanıt üretir (iddia değil): readiness() self-check gerçek runtime'a karşı; graceful shutdown idempotent + hataları
GÖRÜNÜR (Madde 27). Dış adapter gerektirmez — deterministik. Backward-compat: mevcut close() çağrıları çalışır."""

import pytest

from mio_core.runtime import boot, _workspace_writable, _resilience_available, _READINESS_DOMAINS


@pytest.fixture
def mio(tmp_path):
    m = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    yield m
    if not m._closed:
        m.close()


# ---- readiness() self-check ----
def test_readiness_all_green(mio):
    r = mio.readiness()
    assert r["ready"] is True
    c = r["checks"]
    assert c["not_closed"]["ok"] is True
    assert c["event_bus"]["ok"] is True
    assert c["persistence_stores"]["ok"] is True and c["persistence_stores"]["count"] > 30
    assert c["resilience"]["ok"] is True
    assert c["workspace_writable"]["ok"] is True
    # tüm sözleşmeli domainler hazır (contract().version sorgulanabilir)
    assert c["domains"]["ok"] is True and c["domains"]["failed"] == []
    assert c["domains"]["ready"] == c["domains"]["total"] == len(_READINESS_DOMAINS)


def test_readiness_reflects_closed_state(mio):
    assert mio.readiness()["ready"] is True
    mio.close()
    r = mio.readiness()
    assert r["ready"] is False                      # kapandıktan sonra hazır DEĞİL (dürüst)
    assert r["checks"]["not_closed"]["ok"] is False


# ---- graceful shutdown ----
def test_close_returns_structured_report(mio):
    report = mio.close()
    assert report["already_closed"] is False
    assert "persist" in report["closed"]
    assert len(report["closed"]) > 30               # tüm store'lar + kv kapandı
    assert report["errors"] == []                   # normalde hatasız


def test_close_is_idempotent(mio):
    first = mio.close()
    assert first["already_closed"] is False and first["closed"]
    second = mio.close()                            # ikinci çağrı no-op
    assert second["already_closed"] is True and second["closed"] == [] and second["errors"] == []


def test_close_surfaces_errors_not_silent(mio):
    """Madde 27: kapanış hatası sessizce yutulmaz — raporda görünür, ama süreç raise ETMEZ."""
    class _FaultyCloseable:
        def close(self):
            raise RuntimeError("bağlantı zaten kopmuş")
    mio._closeables.append(_FaultyCloseable())
    report = mio.close()                            # raise ETMEZ
    faults = [e for e in report["errors"] if e["component"] == "_FaultyCloseable"]
    assert len(faults) == 1 and "bağlantı zaten kopmuş" in faults[0]["error"]
    # diğer bileşenler yine de kapandı (best-effort)
    assert "persist" in report["closed"]


# ---- config validation yardımcıları (deterministik) ----
def test_workspace_writable_helper(tmp_path):
    ok = _workspace_writable(str(tmp_path / "ws"))
    assert ok["ok"] is True
    # boş workspace (in-memory) sorun değil
    assert _workspace_writable("")["ok"] is True


def test_resilience_layer_available():
    assert _resilience_available() is True          # Madde 28 katmanı yüklenebilir
