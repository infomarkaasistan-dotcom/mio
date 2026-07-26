"""MIO Core · HTTP API adapter (Interface Katmanı #2) — stdlib `http.server`, framework YOK.

HTTP yalnızca bir **ADAPTER**'dır: her istek `mio_core.appservice` (CLI ile PAYLAŞILAN sözleşme yüzeyi) üzerinden
delege edilir — **iş mantığı KOPYALANMAZ** (Madde 15/16). Executive Core'a framework bağımlılığı EKLENMEZ; istenirse
FastAPI/Flask ileride AYRI bir adapter paketi olarak eklenebilir.

Eşzamanlılık: **tek-thread'li `HTTPServer`** (ThreadingHTTPServer DEĞİL) — bilinçli seçim. Repository katmanının
eşzamanlılık sınırı (bkz. PLATFORM_HARDENING.md 'Eşzamanlılık bulgusu') nedeniyle istekler serileştirilir. Çok-thread
sunum, persistence remediasyonu (thread-başına bağlantı) sonrası ele alınacaktır.

Güvenlik: reflektif `call` yüzeyi güçlüdür → sunucu varsayılan olarak **127.0.0.1**'e bağlanır (yerel geliştirme).
Domainlerin kendi authz'i (Madde 24 vb.) her çağrıda yürürlüktedir. Ağ-seviyesi kimlik doğrulama (token/mTLS)
production için ayrı bir katmandır (henüz yok — dürüst kapsam)."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from mio_core import appservice
from mio_core.appservice import BadRequest, NotFound

logger = logging.getLogger("mio.http")

_INDEX = {
    "service": "mio-executive-os",
    "note": "HTTP adapter — CLI ile aynı appservice sözleşmelerini kullanır (iş mantığı kopyalanmaz).",
    "endpoints": {
        "GET /health": "sağlık özeti",
        "GET /readiness": "operasyonel hazırlık (200 ready / 503 not-ready)",
        "GET /metrics": "tüm domain metrikleri",
        "GET /domains": "domain listesi",
        "GET /domains/{name}/contract": "domain sözleşmesi",
        "GET /domains/{name}/stats": "domain metrikleri",
        "GET /events?limit=N": "son olaylar",
        "GET /connectors": "kayıtlı connector'lar (Capability Adapter Layer)",
        "GET /capabilities": "capability → sağlayan connector'lar",
        "POST /domains/{name}/{operation}": "operasyon çağrısı (JSON gövde = kwargs, ör. {\"actor\":\"owner\"})",
        "POST /capabilities/{capability}": "capability çalıştır (JSON gövde=request; ?actor=&approved=)",
    },
}


def _status_for_exception(exc: Exception) -> int:
    """Domain istisnasını HTTP statüsüne eşler (isim-tabanlı; iş mantığı değil)."""
    n = type(exc).__name__
    if isinstance(exc, NotFound) or n == "NotFoundError":
        return 404
    if isinstance(exc, BadRequest) or n in ("ValidationError", "TypeError"):
        return 400
    if n == "UnauthorizedError":
        return 403
    if n == "TransitionError":
        return 409
    return 500


def route_request(mio, method: str, path: str, query: dict, body: Any) -> tuple[int, Any]:
    """HTTP semantiğini appservice'e eşler (SAF, soketsiz test edilebilir). (http_status, data) döner."""
    parts = [p for p in path.strip("/").split("/") if p != ""]
    try:
        if method == "GET":
            if not parts:
                return 200, _INDEX
            if parts == ["health"]:
                return 200, appservice.health(mio)
            if parts == ["readiness"]:
                r = appservice.readiness(mio)
                return (200 if r.get("ready") else 503), r
            if parts == ["metrics"]:
                return 200, appservice.metrics(mio)
            if parts == ["domains"]:
                return 200, appservice.list_domains(mio)
            if parts == ["events"]:
                limit = int(query.get("limit", ["20"])[0]) if query.get("limit") else 20
                return 200, appservice.events(mio, limit)
            if parts == ["connectors"]:
                return 200, appservice.connectors_overview(mio)
            if parts == ["capabilities"]:
                return 200, appservice.capabilities_catalog(mio)
            if len(parts) == 3 and parts[0] == "domains" and parts[2] == "contract":
                return 200, appservice.domain_contract(mio, parts[1])
            if len(parts) == 3 and parts[0] == "domains" and parts[2] == "stats":
                return 200, appservice.domain_stats(mio, parts[1])
            return 404, {"error": f"yol bulunamadı: GET /{path.strip('/')}"}

        if method == "POST":
            # POST /domains/{name}/{operation}  gövde = kwargs (JSON nesne)
            if len(parts) == 3 and parts[0] == "domains":
                if not isinstance(body, dict):
                    return 400, {"error": 'gövde bir JSON nesnesi olmalı, ör: {"actor":"owner","name":"S"}'}
                result = appservice.call(mio, parts[1], parts[2], body)
                return 200, {"result": result}
            # POST /capabilities/{capability}  gövde = request ; ?actor=&approved=true
            if len(parts) == 2 and parts[0] == "capabilities":
                actor = query.get("actor", ["owner"])[0]
                approved = query.get("approved", ["false"])[0].lower() in ("1", "true", "yes")
                outcome = appservice.execute_capability(mio, parts[1], body if isinstance(body, dict) else {},
                                                        actor=actor, user_approved=approved)
                # capability çalıştırma çökmez; connector_unavailable → 503, requires_approval → 403
                status = 200 if outcome.get("ok") else (
                    503 if outcome.get("status") == "connector_unavailable" else
                    403 if outcome.get("status") == "requires_approval" else 502)
                return status, outcome
            return 404, {"error": f"yol bulunamadı: POST /{path.strip('/')}"}

        return 405, {"error": f"desteklenmeyen metod: {method}"}
    except (NotFound, BadRequest) as exc:
        return _status_for_exception(exc), {"error": str(exc), "type": type(exc).__name__}
    except Exception as exc:  # noqa: BLE001 — domain istisnası HTTP statüsüne çevrilir, sunucu çökmez
        return _status_for_exception(exc), {"error": str(exc), "type": type(exc).__name__}


class _Handler(BaseHTTPRequestHandler):
    server_version = "MIO-HTTP/1.0"

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        body: Any = None
        if method == "POST":
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b""
            if raw:
                try:
                    body = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._send(400, {"error": "geçersiz JSON gövde"})
                    return
            else:
                body = {}
        status, data = route_request(self.server.mio, method, parsed.path, query, body)  # type: ignore[attr-defined]
        self._send(status, data)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _send(self, status: int, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False, default=str, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: Any) -> None:  # varsayılan stderr gürültüsünü sustur
        logger.info("http %s", fmt % args)


class MIOHTTPServer(HTTPServer):
    """Canlı runtime'ı tutan tek-thread'li HTTP sunucusu (adapter)."""

    def __init__(self, address, mio) -> None:
        super().__init__(address, _Handler)
        self.mio = mio


def make_server(mio, host: str = "127.0.0.1", port: int = 8080) -> MIOHTTPServer:
    """Sunucuyu oluşturur (serve_forever ÇAĞIRMAZ) — test için thread'de başlatılabilir."""
    return MIOHTTPServer((host, port), mio)


def serve(mio, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Bloklayan sunum (Ctrl-C ile durur). Gerçek deploy için Dockerfile/DEPLOYMENT.md."""
    srv = make_server(mio, host, port)
    logger.info("MIO HTTP adapter %s:%s", host, port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.shutdown()
        srv.server_close()


__all__ = ["route_request", "make_server", "serve", "MIOHTTPServer"]
