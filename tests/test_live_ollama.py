"""MIO Core · CANLI uçtan-uca doğrulama — gerçek Ollama (localhost:11434) ile.

Bu test yalnız Ollama ERİŞİLEBİLİRSE koşar; yoksa ATLANIR → CI (Ollama'sız) yeşil kalır. Amaç: Executive →
advisor.ask() → ConnectorManager → ollama connector → GERÇEK LLM zincirinin canlı çalıştığını KANITLAMAK
(danışman TAVSİYE döner, karar vermez — Madde 1). Model ismi çalışan Ollama'dan alınır (taşınabilir)."""

import json
import os
import urllib.request

import pytest

_OLLAMA = "http://localhost:11434"


def _ollama_models() -> list:
    try:
        with urllib.request.urlopen(f"{_OLLAMA}/api/tags", timeout=3) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:  # noqa: BLE001 — Ollama yok → canlı test atlanır
        return []


# OPT-IN: gerçek LLM çıkarımı AĞIR + sistemi dondurabilir (CPU çıkarımında). Varsayılan ATLANIR;
# yalnız MIO_LIVE_OLLAMA=1 ile koşar (bilinçli, kaynak-farkında çalıştırma). CI'da da atlanır.
_ENABLED = os.environ.get("MIO_LIVE_OLLAMA") == "1"
_MODELS = _ollama_models() if _ENABLED else []
pytestmark = pytest.mark.skipif(
    not _ENABLED or not _MODELS,
    reason="Canlı Ollama testi opt-in (MIO_LIVE_OLLAMA=1) + Ollama erişilebilir olmalı — donmayı önler")


def _small_model() -> str:
    for pref in ("llama3.2:3b", "qwen2.5:3b", "granite-code:3b", "qwen3.5:2b"):
        if pref in _MODELS:
            return pref
    return _MODELS[0]


def _mio(tmp_path):
    from mio_core.runtime import boot
    from mio_core.connectors.adapters import register_from_env
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    register_from_env(mio.connectors, env={"LLM_ENABLED": "true", "MIO_OLLAMA_MODEL": _small_model()},
                      workspace=str(tmp_path / "mio"))
    return mio


def test_live_advisor_ask_via_ollama(tmp_path):
    """Executive → advisor.ask() → CANLI Ollama → gerçek tavsiye (Madde 1: danışman, karar vermez)."""
    mio = _mio(tmp_path)
    try:
        assert mio.advisor.available() is True                 # gerçek health ping (/api/tags)
        mio.connectors.execute("ai.advise", {"prompt": "hi"})  # soğuk-başlangıç: modeli yükle
        out = mio.advisor.ask("Reply with ONLY the number: what is 2 plus 2?")
        assert out["status"] == "executed" and out["connector"] == "ollama"
        advice = out["result"]["advice"]
        assert isinstance(advice, str) and advice.strip() != ""   # GERÇEK LLM yanıtı geldi
    finally:
        mio.close()


def test_live_capability_dispatch_ai_advise(tmp_path):
    """capability ile (isimle değil) → ai.advise gerçek Ollama'ya gider."""
    mio = _mio(tmp_path)
    try:
        mio.connectors.execute("ai.advise", {"prompt": "hi"})  # ısıt
        r = mio.connectors.execute("ai.advise", {"prompt": "Say the word hello only."})
        assert r["ok"] and r["status"] == "executed" and r["connector"] == "ollama"
        assert r["result"]["advice"].strip() != ""
    finally:
        mio.close()
