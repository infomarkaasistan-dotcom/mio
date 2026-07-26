"""MIO Core · Platform · HTTP Server Lifecycle — CLI'dan gömülü HTTP API'yi başlat/durdur/durum, stdlib-only.

MIO tek runtime; HTTP adapter bir arka-plan thread'inde bu runtime'ı sunar. CLI (ve gelecek Dashboard) aynı
Application Services üzerinden sunucuyu yönetir — iş mantığı YOK, yalnız yaşam-döngüsü orkestrasyonu. Aynı süreçte
tek sunucu (idempotent). Runtime'a bir `http_server` durumu iliştirilir."""

from __future__ import annotations

import threading
from typing import Any, Optional


class HTTPServerHandle:
    """Arka-plan HTTP sunucusunun yaşam-döngüsü kolu (tek süreç içi). Runtime'a iliştirilir."""

    def __init__(self, mio) -> None:
        self._mio = mio
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._host = ""
        self._port = 0

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, *, host: str = "127.0.0.1", port: int = 8080) -> dict[str, Any]:
        if self.is_running():
            return {"ok": False, "status": "already_running", "host": self._host, "port": self._port}
        from mio_core.http_api import make_server
        self._server = make_server(self._mio, host, int(port))
        self._host, self._port = host, self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True,
                                        name="mio-http")
        self._thread.start()
        return {"ok": True, "status": "started", "host": self._host, "port": self._port,
                "url": f"http://{self._host}:{self._port}"}

    def stop(self) -> dict[str, Any]:
        if not self.is_running():
            return {"ok": False, "status": "not_running"}
        try:
            self._server.shutdown()
            self._server.server_close()
        except Exception as exc:  # noqa: BLE001 — kapatma hatası görünür, çökmez
            return {"ok": False, "status": "error", "error": str(exc)[:160]}
        self._thread.join(timeout=5)
        self._thread = None
        self._server = None
        return {"ok": True, "status": "stopped"}

    def status(self) -> dict[str, Any]:
        running = self.is_running()
        return {"running": running, "host": self._host if running else None,
                "port": self._port if running else None,
                "url": f"http://{self._host}:{self._port}" if running else None}


__all__ = ["HTTPServerHandle"]
