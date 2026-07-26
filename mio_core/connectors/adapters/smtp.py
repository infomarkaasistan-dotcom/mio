"""MIO Core · Communication Connector · SMTP — GERÇEK e-posta gönderimi (stdlib smtplib).

capability: send_email. `smtp_factory` enjekte edilebilir (test: sahte SMTP; canlı: smtplib.SMTP). Kimlik/sunucu
config ile gelir; eksikse health=False. Gmail/Outlook SMTP de bu adapter'la çalışır (app password + host)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any, Callable, Optional

from ..models import Cap, CallableConnector, ConnectorCategory, ValidationError


def smtp_connector(*, host: str, port: int = 587, user: Optional[str] = None,
                   password: Optional[str] = None, use_tls: bool = True, sender: Optional[str] = None,
                   name: str = "smtp", priority: int = 100,
                   smtp_factory: Callable = smtplib.SMTP) -> CallableConnector:
    def _send(req: dict) -> dict[str, Any]:
        to = req.get("to")
        if not to:
            raise ValidationError("send_email: 'to' gerekli")
        msg = EmailMessage()
        msg["From"] = req.get("from") or sender or user or "mio@localhost"
        msg["To"] = to if isinstance(to, str) else ", ".join(to)
        msg["Subject"] = req.get("subject", "(konu yok)")
        msg.set_content(req.get("body", ""))
        client = smtp_factory(host, port, timeout=req.get("timeout", 30))
        try:
            if use_tls:
                client.starttls()
            if user and password:
                client.login(user, password)
            client.send_message(msg)
        finally:
            client.quit()
        return {"sent": True, "to": msg["To"], "subject": msg["Subject"]}

    return CallableConnector(
        name=name, category=ConnectorCategory.COMMUNICATION,
        handlers={Cap.SEND_EMAIL: _send}, priority=priority, health_fn=lambda: bool(host))


__all__ = ["smtp_connector"]
