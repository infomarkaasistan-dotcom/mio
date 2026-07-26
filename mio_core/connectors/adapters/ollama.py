"""MIO Core · AI Connector · Ollama — GERÇEK yerel LLM (HTTP, anahtar YOK). DANIŞMAN (karar vermez, Madde 1).

capability: ai.advise (/api/generate), ai.embed (/api/embeddings). `urlopen` enjekte edilebilir (test); canlı:
localhost:11434. Ollama çalışmıyorsa health=False → Manager atlar / connector_unavailable (çökmez)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from ._http import http_json
from ..models import Cap, CallableConnector, ConnectorCategory


def ollama_connector(*, host: str = "http://localhost:11434", model: str = "llama3",
                     name: str = "ollama", priority: int = 100, timeout: float = 180.0,
                     urlopen: Optional[Callable] = None) -> CallableConnector:
    base = host.rstrip("/")

    def _advise(req: dict) -> dict[str, Any]:
        # LLM çıkarımı + model yükleme uzun sürebilir → uzun timeout (health ping kısa kalır)
        r = http_json(f"{base}/api/generate", method="POST",
                      body={"model": req.get("model", model), "prompt": req.get("prompt", ""),
                            "stream": False}, timeout=req.get("timeout", timeout), urlopen=urlopen)
        body = r["body"]
        # Danışman TAVSİYE döndürür (karar değil)
        return {"advice": body.get("response", ""), "model": body.get("model", model), "raw": body}

    def _embed(req: dict) -> dict[str, Any]:
        r = http_json(f"{base}/api/embeddings", method="POST",
                      body={"model": req.get("model", model), "prompt": req.get("text", "")},
                      timeout=req.get("timeout", timeout), urlopen=urlopen)
        return {"embedding": r["body"].get("embedding", [])}

    def _health() -> bool:
        try:
            return 200 <= http_json(f"{base}/api/tags", timeout=3, urlopen=urlopen)["status"] < 300
        except Exception:  # noqa: BLE001 — Ollama kapalı = sağlıksız (dürüst)
            return False

    return CallableConnector(
        name=name, category=ConnectorCategory.AI,
        handlers={Cap.AI_ADVISE: _advise, Cap.AI_EMBED: _embed}, priority=priority, health_fn=_health)


__all__ = ["ollama_connector"]
