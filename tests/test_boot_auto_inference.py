"""MIO Core · boot() otomatik yerel çıkarım hazırlığı (prepare_inference / MIO_AUTO_INFERENCE).

MIO açılışta çalışacağı ortamı KENDİSİ hazırlar (opsiyonel, varsayılan KAPALI). Gerçek Ollama/indirme YOK:
local_inference.ensure_ready monkeypatch edilir → deterministik. Varsayılan kapalılık, açık-tetikleme, boot'u
çökertmeme (hata görünür), readiness'e yansıma, event yayını, CLI status doğrulanır."""

import pytest

from mio_core.runtime import boot


def test_auto_inference_off_by_default(tmp_path):
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        assert mio.inference_status is None            # varsayılan: açılışta hazırlık YAPILMAZ
        # readiness inference_status None iken local_inference check'i eklemez
        assert "local_inference" not in mio.readiness()["checks"]
    finally:
        mio.close()


def test_auto_inference_explicit_flag_runs(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_ensure(self, **kw):
        calls["n"] += 1
        return {"ready": True, "selected_model": "mistral:7b",
                "message": "TEST BAŞARILI · Ollama bağlı · model=mistral:7b · 900ms · GPU"}

    monkeypatch.setattr("mio_core.platform.local_inference.LocalInferenceManager.ensure_ready", fake_ensure)
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False,
               prepare_inference=True)
    try:
        assert calls["n"] == 1                         # açılışta bir kez hazırlandı
        assert mio.inference_status["ready"] is True and mio.inference_status["selected_model"] == "mistral:7b"
        # readiness'e bilgi olarak yansır (bloklamaz)
        li = mio.readiness()["checks"]["local_inference"]
        assert li["ok"] is True and li["prepared"] is True and li["model"] == "mistral:7b"
        # olay yayınlandı
        assert any(e["type"] == "inference.prepared" for e in mio.bus.history())
        # CLI: inference status → hazırlık sonucu
        from mio_core.cli import run_command
        import json
        code, out = run_command(mio, ["inference", "status"])
        assert code == 0 and json.loads(out)["ready"] is True
    finally:
        mio.close()


def test_auto_inference_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MIO_AUTO_INFERENCE", "1")
    monkeypatch.setattr("mio_core.platform.local_inference.LocalInferenceManager.ensure_ready",
                        lambda self, **kw: {"ready": False, "selected_model": None,
                                            "message": "Ollama çalışmıyor."})
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        assert mio.inference_status is not None and mio.inference_status["ready"] is False
    finally:
        mio.close()


def test_auto_inference_failure_does_not_crash_boot(tmp_path, monkeypatch):
    def boom(self, **kw):
        raise RuntimeError("ollama patladı")
    monkeypatch.setattr("mio_core.platform.local_inference.LocalInferenceManager.ensure_ready", boom)
    # boot ÇÖKMEZ; hata inference_status'ta görünür (dürüst)
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False,
               prepare_inference=True)
    try:
        assert mio.inference_status["ready"] is False and "ollama patladı" in mio.inference_status["error"]
        assert mio.readiness()["ready"] is True        # çekirdek yine hazır (çıkarım opsiyonel)
    finally:
        mio.close()
