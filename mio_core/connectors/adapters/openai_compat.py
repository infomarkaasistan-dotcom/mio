"""MIO Core · AI Connector · OpenAI-uyumlu — GERÇEK bulut LLM (HTTP). DANIŞMAN (karar vermez, Madde 1).

capability: ai.advise (/chat/completions). OpenAI + DeepSeek + Qwen + birçok sağlayıcı AYNI şemayı kullanır →
tek adapter (base_url ile ayrışır). Anahtar config'ten; yoksa health=False → connector_unavailable (çökmez).
`urlopen` enjekte edilebilir (test). Anahtar ASLA loglanmaz."""

from __future__ import annotations

from typing import Any, Callable, Optional

from ._http import http_json
from ..models import Cap, CallableConnector, ConnectorCategory, ValidationError


def openai_connector(*, api_key: str, base_url: str = "https://api.openai.com/v1",
                     model: str = "gpt-4o-mini", name: str = "openai", priority: int = 90,
                     urlopen: Optional[Callable] = None) -> CallableConnector:
    base = base_url.rstrip("/")

    def _advise(req: dict) -> dict[str, Any]:
        if not api_key:
            raise ValidationError("api_key yapılandırılmamış")
        messages = req.get("messages") or [{"role": "user", "content": req.get("prompt", "")}]
        r = http_json(f"{base}/chat/completions", method="POST",
                      body={"model": req.get("model", model), "messages": messages},
                      headers={"Authorization": f"Bearer {api_key}"}, urlopen=urlopen)
        body = r["body"]
        choices = body.get("choices") or [{}]
        advice = (choices[0].get("message") or {}).get("content", "")
        # Danışman TAVSİYE döndürür (karar değil)
        return {"advice": advice, "model": body.get("model", model), "usage": body.get("usage")}

    return CallableConnector(
        name=name, category=ConnectorCategory.AI,
        handlers={Cap.AI_ADVISE: _advise}, priority=priority, health_fn=lambda: bool(api_key))


__all__ = ["openai_connector"]
