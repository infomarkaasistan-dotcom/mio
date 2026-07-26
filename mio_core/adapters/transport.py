"""MIO Core · MCP Transport katmanı — TAM SOYUT, PLUGIN-TABANLI (Öncelik 1), stdlib-only.

MCP'nin transportu (STDIO / HTTP / HTTPS / SSE / WebSocket / Named Pipe / Unix Socket / gelecek) değişince
Executive · Capability · Brain · Tool Orchestrator HİÇBİR ŞEY HİSSETMEZ. Hepsi aynı `MCPTransport`
arayüzünü kullanır. Yeni transport = `TransportRegistry.register(scheme, factory)` — çekirdeğe dokunmadan.

Bu, "çekirdeği büyütme, ekosistemi büyüt" ilkesinin transport katmanındaki uygulamasıdır.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

__all__ = [
    "MCPServerConfig", "JsonRpcError", "MCPTransport",
    "StdioTransport", "HttpTransport", "TransportRegistry", "build_transport",
]


@dataclass
class MCPServerConfig:
    name: str
    command: list[str] = field(default_factory=list)     # stdio için
    env: dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    trust_level: str = "untrusted"
    transport: str = "stdio"                              # stdio | http | https | sse | ws | ... (plugin)
    url: str = ""                                        # http/https/sse için
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0


class JsonRpcError(Exception):
    pass


class MCPTransport(Protocol):
    """Her transport bu arayüzü uygular. Üst katmanlar transportu bilmez."""
    def request(self, method: str, params: Optional[dict] = None) -> dict: ...
    def is_alive(self) -> bool: ...
    def close(self) -> None: ...


_INIT_PARAMS = {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "mio-executive-os", "version": "0.1.0"}}


# --------------------------------------------------------------------------- #
# STDIO transport (yerel MCP sunucuları — npx/uvx)
# --------------------------------------------------------------------------- #
class StdioTransport:
    """MCP JSON-RPC over stdio (newline-delimited). Sunucuyu subprocess olarak başlatır."""

    def __init__(self, command: list[str], *, env: Optional[dict] = None, cwd: Optional[str] = None,
                 timeout: float = 30.0) -> None:
        import os
        self._proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={**os.environ, **(env or {})}, cwd=cwd, text=True, encoding="utf-8", bufsize=1)
        self._id = 0
        self._initialized = False

    def _send(self, obj: dict) -> None:
        if self._proc.stdin is None:
            raise JsonRpcError("MCP stdin kapalı")
        self._proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _read_result(self, want_id: int) -> dict:
        while True:
            if self._proc.stdout is None:
                raise JsonRpcError("MCP stdout kapalı")
            line = self._proc.stdout.readline()
            if not line:
                raise JsonRpcError("MCP sunucu bağlantısı kapandı")
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == want_id:
                if "error" in msg:
                    raise JsonRpcError(str(msg["error"]))
                return msg.get("result", {})

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": "initialize", "params": _INIT_PARAMS})
        self._read_result(self._id)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    def request(self, method: str, params: Optional[dict] = None) -> dict:
        self._ensure_init()
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        return self._read_result(self._id)

    def is_alive(self) -> bool:
        return self._proc.poll() is None

    def close(self) -> None:
        try:
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            try:
                self._proc.kill()
            except Exception:  # noqa: BLE001
                pass


# --------------------------------------------------------------------------- #
# HTTP / SSE transport (barındırılan MCP sunucuları — Streamable HTTP)
# --------------------------------------------------------------------------- #
# (url, body_bytes, headers, timeout) -> (status, response_headers, body_text)
HttpPoster = Callable[[str, bytes, dict, float], tuple]


def _http_post_raw(url: str, body: bytes, headers: dict, timeout: float) -> tuple:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.status, {k: v for k, v in resp.headers.items()}, resp.read().decode("utf-8")


def _parse_body(body: str) -> dict:
    """JSON ya da SSE (text/event-stream) gövdesinden JSON-RPC mesajını çıkarır."""
    text = body.strip()
    if not text:
        return {}
    if text.startswith("{"):
        return json.loads(text)
    # SSE: 'data: {...}' satırlarını topla
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                try:
                    msg = json.loads(payload)
                    if isinstance(msg, dict) and ("result" in msg or "error" in msg or "id" in msg):
                        return msg
                except json.JSONDecodeError:
                    continue
    return json.loads(text)  # son çare


class HttpTransport:
    """MCP Streamable HTTP transport (HTTP/HTTPS/SSE). JSON-RPC POST; Mcp-Session-Id yönetir; JSON ya da
    SSE yanıtı ayrıştırır. `post` enjekte edilebilir (test). Üst katmanlar bunu StdioTransport'tan ayırt etmez."""

    def __init__(self, url: str, *, headers: Optional[dict] = None, timeout: float = 30.0,
                 post: Optional[HttpPoster] = None) -> None:
        self._url = url
        self._headers = {"Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream", **(headers or {})}
        self._timeout = timeout
        self._post = post or _http_post_raw
        self._id = 0
        self._session: Optional[str] = None
        self._initialized = False

    def _rpc(self, method: str, params: Optional[dict], *, notify: bool = False) -> dict:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not notify:
            self._id += 1
            payload["id"] = self._id
        if params:
            payload["params"] = params
        headers = dict(self._headers)
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        status, rheaders, body = self._post(
            self._url, json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers, self._timeout)
        sid = rheaders.get("Mcp-Session-Id") or rheaders.get("mcp-session-id")
        if sid:
            self._session = sid
        if notify:
            return {}
        msg = _parse_body(body)
        if "error" in msg:
            raise JsonRpcError(str(msg["error"]))
        return msg.get("result", {})

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._rpc("initialize", _INIT_PARAMS)
        self._rpc("notifications/initialized", None, notify=True)
        self._initialized = True

    def request(self, method: str, params: Optional[dict] = None) -> dict:
        self._ensure_init()
        return self._rpc(method, params or {})

    def is_alive(self) -> bool:
        return True                                     # durumsuz HTTP; sağlık ayrı health-check ile

    def close(self) -> None:
        pass


# --------------------------------------------------------------------------- #
# Transport Registry (PLUGIN) — scheme → factory. Yeni transport çekirdeği değiştirmeden eklenir.
# --------------------------------------------------------------------------- #
class TransportRegistry:
    _factories: dict[str, Callable[[MCPServerConfig], MCPTransport]] = {}

    @classmethod
    def register(cls, scheme: str, factory: Callable[[MCPServerConfig], MCPTransport]) -> None:
        cls._factories[scheme] = factory

    @classmethod
    def build(cls, config: MCPServerConfig) -> MCPTransport:
        factory = cls._factories.get(config.transport)
        if factory is None:
            raise JsonRpcError(f"Desteklenmeyen transport: '{config.transport}' "
                               f"(kayıtlı: {', '.join(sorted(cls._factories)) or 'yok'})")
        return factory(config)

    @classmethod
    def schemes(cls) -> list[str]:
        return sorted(cls._factories)


# Varsayılan transportları kaydet (plugin: yenileri register ile eklenir).
TransportRegistry.register("stdio", lambda c: StdioTransport(c.command, env=c.env, cwd=c.cwd, timeout=c.timeout))
TransportRegistry.register("http", lambda c: HttpTransport(c.url, headers=c.headers, timeout=c.timeout))
TransportRegistry.register("https", lambda c: HttpTransport(c.url, headers=c.headers, timeout=c.timeout))
TransportRegistry.register("sse", lambda c: HttpTransport(c.url, headers=c.headers, timeout=c.timeout))


def build_transport(config: MCPServerConfig) -> MCPTransport:
    """Config'e göre uygun transportu (plugin) üretir. Üst katmanlar bunu bilmez."""
    return TransportRegistry.build(config)
