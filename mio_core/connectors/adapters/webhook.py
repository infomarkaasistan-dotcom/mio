"""MIO Core · Communication Connector · Webhook — GERÇEK mesaj gönderimi (HTTP POST).

capability: send_message. Slack/Discord/Telegram-bot/generic webhook URL'lerinin HEPSİ POST kabul eder → tek
adapter hepsini kapsar. `payload_style` biçimi ayarlar (slack:{text}, discord:{content}, telegram:{chat_id,text},
raw). `urlopen` enjekte edilebilir (test)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from ._http import http_json
from ..models import Cap, CallableConnector, ConnectorCategory, ValidationError


def _shape(style: str, req: dict) -> dict:
    text = req.get("text", req.get("message", ""))
    if style == "slack":
        return {"text": text}
    if style == "discord":
        return {"content": text}
    if style == "telegram":
        return {"chat_id": req.get("chat_id"), "text": text}
    return req.get("payload", {"text": text})   # raw/generic


def webhook_connector(*, url: str, payload_style: str = "slack", name: str = "webhook", priority: int = 100,
                      headers: Optional[dict] = None, urlopen: Optional[Callable] = None) -> CallableConnector:
    def _send(req: dict) -> dict[str, Any]:
        if not url:
            raise ValidationError("webhook url yapılandırılmamış")
        resp = http_json(url, method="POST", body=_shape(payload_style, req), headers=headers,
                         urlopen=urlopen)
        return {"sent": 200 <= resp["status"] < 300, "status": resp["status"], "style": payload_style}

    return CallableConnector(
        name=name, category=ConnectorCategory.COMMUNICATION,
        handlers={Cap.SEND_MESSAGE: _send}, priority=priority, health_fn=lambda: bool(url))


__all__ = ["webhook_connector"]
