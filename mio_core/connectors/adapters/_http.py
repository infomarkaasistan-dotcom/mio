"""MIO Core · Connector adapters · paylaşılan HTTP yardımcısı (stdlib urllib, enjekte-edilebilir → test)."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Optional


def http_json(url: str, *, method: str = "GET", body: Any = None, headers: Optional[dict] = None,
              timeout: float = 30.0, urlopen: Optional[Callable] = None) -> dict[str, Any]:
    """JSON istek/yanıt. urlopen enjekte edilebilir (varsayılan gerçek). Hata GÖRÜNÜR (raise), çağıran yakalar."""
    opener = urlopen or urllib.request.urlopen
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    with opener(req, timeout=timeout) as resp:
        raw = resp.read()
        status = getattr(resp, "status", 200) or 200
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"raw": raw.decode("utf-8", "replace")[:2000]}
        return {"status": status, "body": payload}


def http_text(url: str, *, method: str = "GET", data: Optional[bytes] = None, headers: Optional[dict] = None,
              timeout: float = 30.0, urlopen: Optional[Callable] = None) -> dict[str, Any]:
    """Ham metin istek (CalDAV PUT/REPORT vb.). (status, text) döner."""
    opener = urlopen or urllib.request.urlopen
    req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    with opener(req, timeout=timeout) as resp:
        raw = resp.read()
        return {"status": getattr(resp, "status", 200) or 200, "text": raw.decode("utf-8", "replace")}


__all__ = ["http_json", "http_text"]
