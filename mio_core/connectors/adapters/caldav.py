"""MIO Core · Productivity Connector · CalDAV — GERÇEK takvim (HTTP; iCloud/Nextcloud/Fastmail/Google app-pwd).

capability: calendar.create_event (iCalendar .ics PUT), calendar.list_events (REPORT). CalDAV açık standarttır →
tek adapter birçok sağlayıcıyı kapsar (OAuth yerine app-password + collection URL). `urlopen` enjekte edilebilir
(test). Kimlik eksikse health=False. calendar.create_event dış-yazım → Manager Madde 24 kapsamı dışıdır (opsiyonel;
istenirse HIGH_RISK'e eklenir)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import uuid4

from ._http import http_text
from ..models import Cap, CallableConnector, ConnectorCategory, ValidationError


def _ics(summary: str, start: str, end: str, uid: str) -> str:
    dt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//MIO//caldav//TR\r\nBEGIN:VEVENT\r\n"
            f"UID:{uid}\r\nDTSTAMP:{dt}\r\nDTSTART:{start}\r\nDTEND:{end}\r\nSUMMARY:{summary}\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n")


def caldav_connector(*, url: str, user: str, password: str, name: str = "caldav", priority: int = 100,
                     urlopen: Optional[Callable] = None) -> CallableConnector:
    base = url.rstrip("/")

    def _auth() -> dict:
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def _create(req: dict) -> dict[str, Any]:
        if not (url and user):
            raise ValidationError("caldav yapılandırılmamış")
        summary = req.get("summary")
        start, end = req.get("start"), req.get("end")
        if not (summary and start and end):
            raise ValidationError("calendar.create_event: summary, start, end gerekli (iCal: 20260101T090000Z)")
        uid = req.get("uid") or f"{uuid4().hex}@mio"
        r = http_text(f"{base}/{uid}.ics", method="PUT", data=_ics(summary, start, end, uid).encode("utf-8"),
                      headers={**_auth(), "Content-Type": "text/calendar; charset=utf-8"}, urlopen=urlopen)
        return {"created": 200 <= r["status"] < 300, "status": r["status"], "uid": uid}

    def _list(req: dict) -> dict[str, Any]:
        report = ('<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
                  '<d:prop><d:getetag/><c:calendar-data/></d:prop>'
                  '<c:filter><c:comp-filter name="VCALENDAR"/></c:filter></c:calendar-query>')
        r = http_text(base, method="REPORT",
                      data=report.encode("utf-8"),
                      headers={**_auth(), "Depth": "1", "Content-Type": "application/xml"}, urlopen=urlopen)
        return {"status": r["status"], "raw": r["text"][:4000]}

    return CallableConnector(
        name=name, category=ConnectorCategory.PRODUCTIVITY,
        handlers={Cap.CALENDAR_CREATE: _create, Cap.CALENDAR_LIST: _list},
        priority=priority, health_fn=lambda: bool(url and user))


__all__ = ["caldav_connector"]
