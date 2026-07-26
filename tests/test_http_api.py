"""MIO Core · HTTP API adapter (Interface Katmanı #2) — stdlib http.server KANITI.

route_request saf (soketsiz) eşleme + gerçek soket üstünden uçtan-uca + CLI ile AYNI appservice'i kullandığının
kanıtı (iş mantığı kopyalanmaz). Deterministik; framework yok."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from mio_core.runtime import boot, _READINESS_DOMAINS
from mio_core.http_api import route_request, make_server


@pytest.fixture
def mio(tmp_path):
    m = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    yield m
    m.close()


# ---- SAF route_request (soketsiz) ----
def test_get_routes(mio):
    assert route_request(mio, "GET", "/health", {}, None)[0] == 200
    st, r = route_request(mio, "GET", "/readiness", {}, None)
    assert st == 200 and r["ready"] is True
    assert route_request(mio, "GET", "/metrics", {}, None)[1]["domain_count"] == 24
    st, doc = route_request(mio, "GET", "/domains", {}, None)
    assert st == 200 and len(doc) == len(_READINESS_DOMAINS)
    assert route_request(mio, "GET", "/domains/iot/contract", {}, None)[1]["domain"] == "iot"
    assert route_request(mio, "GET", "/domains/iot/stats", {}, None)[1]["contract_version"] == "1.0.0"
    assert route_request(mio, "GET", "/events", {"limit": ["5"]}, None)[0] == 200
    assert route_request(mio, "GET", "/yok", {}, None)[0] == 404
    assert route_request(mio, "GET", "/domains/yok/contract", {}, None)[0] == 404


def test_post_call_and_error_mapping(mio):
    st, out = route_request(mio, "POST", "/domains/iot/register_thing", {},
                            {"actor": "owner", "name": "Kazan", "kind": "sensor"})
    assert st == 200 and out["result"]["name"] == "Kazan"
    # yetki hatası (domain authz) → 403 (aynı appservice üzerinden, Madde 24 yürürlükte)
    st, out = route_request(mio, "POST", "/domains/iot/register_thing", {},
                            {"actor": "Reasoning", "name": "x"})
    assert st == 403 and out["type"] == "UnauthorizedError"
    # validation hatası → 400
    st, out = route_request(mio, "POST", "/domains/iot/register_thing", {},
                            {"actor": "owner", "name": "x", "kind": "uydurma"})
    assert st == 400 and out["type"] == "ValidationError"
    # bilinmeyen domain → 404 ; gövde dict değil → 400 ; özel metod → 400
    assert route_request(mio, "POST", "/domains/yok/op", {}, {})[0] == 404
    assert route_request(mio, "POST", "/domains/iot/register_thing", {}, [1, 2])[0] == 400
    assert route_request(mio, "POST", "/domains/iot/_private", {}, {})[0] == 400


def test_connector_routes(mio):
    assert route_request(mio, "GET", "/connectors", {}, None)[0] == 200
    assert route_request(mio, "GET", "/capabilities", {}, None)[0] == 200
    # POST /capabilities/{cap} — connector yok → 503 connector_unavailable (çökmez)
    st, out = route_request(mio, "POST", "/capabilities/send_email", {}, {"to": "a@b.com"})
    assert st == 503 and out["status"] == "connector_unavailable"
    # yüksek-risk onaysız → 403 requires_approval (önce fake connector bağla)
    from mio_core.connectors import CallableConnector, ConnectorCategory, Cap
    mio.connectors.register(CallableConnector("shell", ConnectorCategory.SYSTEM,
                                              handlers={Cap.SHELL_EXEC: lambda r: {"ran": r.get("cmd")}}))
    st, out = route_request(mio, "POST", "/capabilities/shell.exec", {}, {"cmd": "ls"})
    assert st == 403 and out["status"] == "requires_approval"
    st, out = route_request(mio, "POST", "/capabilities/shell.exec", {"approved": ["true"]}, {"cmd": "ls"})
    assert st == 200 and out["ok"] is True


def test_readiness_503_when_closed(tmp_path):
    m = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    m.close()
    st, r = route_request(m, "GET", "/readiness", {}, None)
    assert st == 503 and r["ready"] is False        # kapandıktan sonra 503 (dürüst)


# ---- Gerçek soket üstünden uçtan-uca ----
@pytest.fixture
def server(mio):
    srv = make_server(mio, "127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()
    srv.server_close()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, json.load(r)


def _post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode("utf-8"),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.load(r)


def test_live_http_get_and_post(server):
    assert _get(server, "/readiness")[1]["ready"] is True
    assert len(_get(server, "/domains")[1]) == 24
    st, out = _post(server, "/domains/iot/register_thing",
                    {"actor": "owner", "name": "Saha", "kind": "sensor"})
    assert st == 200 and out["result"]["name"] == "Saha"


def test_live_http_error_status(server):
    with pytest.raises(urllib.error.HTTPError) as ei:
        _post(server, "/domains/iot/register_thing", {"actor": "Reasoning", "name": "x"})
    assert ei.value.code == 403                     # gerçek HTTP 403 (domain authz)
    with pytest.raises(urllib.error.HTTPError) as ei2:
        _get(server, "/nope")
    assert ei2.value.code == 404


# ---- CLI ile HTTP AYNI appservice'i kullanır (iş mantığı kopyalanmaz) ----
def test_http_and_cli_share_appservice(mio):
    from mio_core.cli import run_command
    # CLI domains == HTTP /domains (aynı kaynak → aynı sonuç)
    _c, cli_out = run_command(mio, ["domains"])
    cli_domains = {d["domain"] for d in json.loads(cli_out)}
    _s, http_domains_doc = route_request(mio, "GET", "/domains", {}, None)
    http_domains = {d["domain"] for d in http_domains_doc}
    assert cli_domains == http_domains and "iot" in cli_domains
    # her ikisi de appservice.list_domains'e delege eder
    from mio_core import appservice
    assert {d["domain"] for d in appservice.list_domains(mio)} == cli_domains
