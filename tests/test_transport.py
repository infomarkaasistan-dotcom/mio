"""MIO Core · MCP Transport (plugin) — üretim testleri (HTTP boundary test double ile)."""

import json

import pytest

from mio_core.adapters import (
    HttpTransport,
    MCPServerConfig,
    StdioMCPClient,
    TransportRegistry,
    build_transport,
)
from mio_core.adapters.transport import JsonRpcError, _parse_body


class FakeHttp:
    """MCP Streamable HTTP sunucusunu taklit eden post fonksiyonu (test double)."""

    def __init__(self, tools, call_result="ok", session="sess-1"):
        self._tools = tools
        self._call_result = call_result
        self._session = session
        self.sent_session = None

    def __call__(self, url, body, headers, timeout):
        req = json.loads(body.decode("utf-8"))
        method, rid = req.get("method"), req.get("id")
        rheaders = {"Mcp-Session-Id": self._session}
        if method == "initialize":
            return 200, rheaders, json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05"}})
        if method == "notifications/initialized":
            return 202, rheaders, ""
        if method == "tools/list":
            return 200, rheaders, json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"tools": self._tools}})
        if method == "tools/call":
            self.sent_session = headers.get("Mcp-Session-Id")
            return 200, rheaders, json.dumps(
                {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": self._call_result}]}})
        return 200, rheaders, json.dumps({"jsonrpc": "2.0", "id": rid, "result": {}})


def test_http_transport_request_and_session():
    fake = FakeHttp([{"name": "read_file"}], call_result="içerik")
    tr = HttpTransport("http://x/mcp", post=fake)
    listed = tr.request("tools/list")
    assert listed["tools"][0]["name"] == "read_file"
    res = tr.request("tools/call", {"name": "read_file", "arguments": {}})
    assert res["content"][0]["text"] == "içerik"
    assert fake.sent_session == "sess-1"                 # Mcp-Session-Id sonraki isteklere taşındı


def test_sse_body_parsing():
    body = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
    assert _parse_body(body)["result"]["ok"] is True


def test_registry_has_default_schemes():
    schemes = TransportRegistry.schemes()
    for s in ("stdio", "http", "https", "sse"):
        assert s in schemes


def test_build_transport_by_scheme():
    t = build_transport(MCPServerConfig("x", transport="http", url="http://y/mcp"))
    assert isinstance(t, HttpTransport)


def test_unsupported_transport_is_honest():
    with pytest.raises(JsonRpcError):
        build_transport(MCPServerConfig("x", transport="quantum"))


def test_plugin_transport_registration():
    """Yeni transport çekirdeğe dokunmadan eklenir (plugin)."""
    class DummyTransport:
        def __init__(self, cfg):
            self.cfg = cfg
        def request(self, method, params=None):
            return {}
        def is_alive(self):
            return True
        def close(self):
            pass
    TransportRegistry.register("dummy", lambda c: DummyTransport(c))
    assert "dummy" in TransportRegistry.schemes()
    assert isinstance(build_transport(MCPServerConfig("x", transport="dummy")), DummyTransport)


def test_http_through_mcp_client_transport_agnostic():
    """MCP client transportu bilmez: http config → hiçbir üst katman değişmeden çalışır."""
    fake = FakeHttp([{"name": "read_file"}], call_result="okundu")
    client = StdioMCPClient([MCPServerConfig("fs", transport="http", url="http://x/mcp")],
                            transport_factory=lambda c: HttpTransport(c.url, post=fake))
    servers = client.discover()
    assert servers[0].status == "healthy" and servers[0].transport == "http"
    assert client.call(servers[0], "read_file", {"path": "a"}) == "okundu"
