"""MIO Core · Ollama adaptörü — GERÇEK yerel LLM sağlayıcısı (üretim), stdlib-only (urllib).

Model Gateway'i (X4) kullanıcının makinesinde çalışan GERÇEK Ollama örneğine bağlar:
  - `OllamaProvider` → `ModelProvider`: /api/generate ile gerçek üretim.
  - `wire_ollama(gateway)` → /api/tags ile kurulu modelleri KEŞFEDER ve gateway'e kaydeder (donanım-farkında
    kalite/hız metadatası). Böylece "llm" yeteneği gerçekten bağlı olur.

HTTP çağrıları enjekte edilebilir (test için) — varsayılan gerçek urllib. Ollama erişilemezse dürüstçe
Exception fırlatır (gateway failover eder / "llm" bağlanmaz); çekirdek LLM-siz çalışmaya devam eder.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Optional

from mio_core.execution.model_gateway import ModelGateway, ModelSpec

__all__ = ["OllamaProvider", "wire_ollama", "http_post_json", "http_get_json"]

PostJson = Callable[[str, dict, float], dict]
GetJson = Callable[[str, float], dict]


def http_post_json(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — yerel Ollama
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url: str, timeout: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


class OllamaProvider:
    """GERÇEK Ollama sağlayıcısı (ModelProvider). Başarıda metin döner, başarısızlıkta Exception."""

    def __init__(self, base_url: str = "http://localhost:11434", *, timeout: float = 120.0,
                 post_json: Optional[PostJson] = None) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._post = post_json or http_post_json

    def generate(self, model: ModelSpec, prompt: str, system: Optional[str], max_tokens: int) -> str:
        payload: dict[str, Any] = {
            "model": model.name, "prompt": prompt, "stream": False,
            "options": {"num_predict": int(max_tokens)},
        }
        if system:
            payload["system"] = system
        data = self._post(f"{self._base}/api/generate", payload, self._timeout)
        text = data.get("response")
        if not text:
            raise RuntimeError(f"Ollama boş yanıt döndü (model={model.name}).")
        return text


def _quality_for(size_gb: float) -> float:
    """Model boyutundan kaba kalite tahmini (yerel modeller için makul heuristik)."""
    return round(min(0.9, 0.45 + size_gb * 0.03), 2)


def _speed_for(size_gb: float) -> float:
    """Büyük model = daha yavaş (yerel CPU/GPU)."""
    return round(max(0.2, 0.9 - size_gb * 0.04), 2)


def wire_ollama(gateway: ModelGateway, *, base_url: str = "http://localhost:11434",
                timeout: float = 120.0, provider: Optional[OllamaProvider] = None,
                get_json: Optional[GetJson] = None, post_json: Optional[PostJson] = None) -> int:
    """Çalışan Ollama'daki kurulu modelleri KEŞFEDER ve gateway'e kaydeder. Döner: kaydedilen model sayısı.
    Ollama erişilemezse Exception fırlatır (çağıran dürüstçe ele alır — 'llm' bağlanmaz)."""
    getj = get_json or http_get_json
    provider = provider or OllamaProvider(base_url, timeout=timeout, post_json=post_json)
    tags = getj(f"{base_url.rstrip('/')}/api/tags", timeout)
    n = 0
    for m in tags.get("models", []):
        name = m.get("name")
        if not name:
            continue
        size_gb = float(m.get("size", 0)) / 1e9
        spec = ModelSpec(name=name, provider="ollama", local=True, cost=0.0,
                         quality=_quality_for(size_gb), speed=_speed_for(size_gb),
                         context=int(m.get("context", 8192)))
        gateway.register_model(spec, provider)
        n += 1
    return n
