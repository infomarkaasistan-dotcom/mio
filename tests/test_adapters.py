"""MIO Core · Adaptörler — üretim testleri (HTTP boundary test double ile; donanım gerçek stdlib)."""

import pytest

from mio_core.adapters.hardware import discover_hardware
from mio_core.adapters.ollama import OllamaProvider, wire_ollama
from mio_core.execution import ModelGateway
from mio_core.execution.model_gateway import ModelSpec


# ---- Ollama provider (gerçek adaptör, sahte transport) ----
def test_ollama_generate():
    def fake_post(url, payload, timeout):
        assert url.endswith("/api/generate") and payload["model"] == "llama3.2:3b"
        assert payload["stream"] is False
        return {"response": "merhaba dünya"}

    p = OllamaProvider(post_json=fake_post)
    out = p.generate(ModelSpec("llama3.2:3b", "ollama"), "selam", None, 10)
    assert out == "merhaba dünya"


def test_ollama_empty_response_raises():
    p = OllamaProvider(post_json=lambda url, payload, timeout: {"response": ""})
    with pytest.raises(RuntimeError):
        p.generate(ModelSpec("m", "ollama"), "x", None, 5)


def test_wire_ollama_discovers_and_registers_models():
    gw = ModelGateway()

    def fake_tags(url, timeout):
        assert url.endswith("/api/tags")
        return {"models": [{"name": "llama3.2:3b", "size": 2_000_000_000},
                           {"name": "qwen3:14b", "size": 9_300_000_000}]}

    n = wire_ollama(gw, get_json=fake_tags, post_json=lambda *a: {"response": "x"})
    assert n == 2
    assert set(gw.connected_models()) == {"llama3.2:3b", "qwen3:14b"}
    # büyük model daha yüksek kalite, daha düşük hız (donanım-farkında metadata)
    specs = {m.name: m for m in gw._models}
    assert specs["qwen3:14b"].quality > specs["llama3.2:3b"].quality
    assert specs["qwen3:14b"].speed < specs["llama3.2:3b"].speed


# ---- Donanım keşfi (GERÇEK stdlib) ----
def test_discover_hardware_real():
    info = discover_hardware()
    assert info["platform"] and info["system"]
    assert isinstance(info["cpu_count"], int) and info["cpu_count"] >= 1
    assert "gpu" in info                              # nvidia | apple_silicon | unknown (dürüst)
