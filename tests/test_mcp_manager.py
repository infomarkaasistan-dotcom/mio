"""MIO Core · MCP Manager — runtime verification + CLI/HTTP entegrasyonu (kullanıcı direktifi).

MCP Manager IMPLEMENTED + INITIALIZED (mio.mcp_management + mio.mcp_hub); eksik olan yalnız CLI/HTTP yüzeyiydi.
Kapsam: initialization, config/wiring, discovery, register/remove, enable(activate), trust, health, CLI, HTTP —
hepsi appservice'e delege (iş mantığı CLI'da YOK). Placeholder yok; boş durum dürüst ([] / stats 0)."""

import json

import pytest

from mio_core.runtime import boot
from mio_core import appservice
from mio_core.cli import run_command, dispatch
from mio_core.http_api import route_request
from mio_core.cli_ui import UI


@pytest.fixture
def mio(tmp_path):
    m = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    yield m
    m.close()


# ---- 1) initialization + wiring ----
def test_mcp_manager_initialized_and_wired(mio):
    assert mio.mcp_management is not None and type(mio.mcp_management).__name__ == "MCPManagementDomain"
    assert mio.mcp_hub is not None                     # hub her zaman var (Madde: MCP Management onu yönetir)
    assert "register_server" in mio.mcp_management.contract()["operations"]


# ---- 2) boş durum DÜRÜST (placeholder yok) ----
def test_mcp_empty_state_is_honest(mio):
    assert appservice.mcp_list(mio) == []              # server yok → boş liste (uydurma değil)
    st = appservice.mcp_stats(mio)
    assert st["servers"] == 0 and st["healthy"] == 0
    assert appservice.mcp_status(mio)["health"] == {}


# ---- 3) register (install) + list + info + remove (uninstall) ----
def test_mcp_register_info_remove(mio):
    srv = appservice.mcp_register(mio, "filesystem-mcp", transport="stdio", trust_level="trusted")
    sid = srv["id"]
    assert srv["name"] == "filesystem-mcp" and srv["trust_level"] == "trusted"
    listed = appservice.mcp_list(mio)
    assert len(listed) == 1 and listed[0]["id"] == sid
    info = appservice.mcp_info(mio, sid)
    assert info["id"] == sid
    rem = appservice.mcp_remove(mio, sid)
    assert rem["removed"] == sid and appservice.mcp_list(mio) == []


# ---- 4) discovery + health ----
def test_mcp_discover_and_health(mio):
    d = appservice.mcp_discover(mio)
    assert "discovered" in d and "servers" in d        # istemci yoksa 0 (dürüst)
    assert isinstance(appservice.mcp_status(mio)["health"], dict)


# ---- 5) trust (enable/disable eşdeğeri) + activate ----
def test_mcp_trust_and_activate(mio):
    srv = appservice.mcp_register(mio, "srv", trust_level="untrusted")
    t = appservice.mcp_trust(mio, srv["id"], "verified")
    assert t.get("trust_level") == "verified" or t.get("trust") == "verified" or "verified" in json.dumps(t)
    act = appservice.mcp_activate(mio)
    assert isinstance(act, dict)                       # aktivasyon DTO (bağlı capability sayısı vb.)


# ---- 6) validation: geçersiz transport reddedilir (domain authz/validation yürürlükte) ----
def test_mcp_register_validation(mio):
    with pytest.raises(Exception):
        appservice.mcp_register(mio, "x", transport="uydurma")


# ---- 7) CLI entegrasyonu (iş mantığı yok — appservice delege) ----
def test_mcp_cli_commands(mio):
    assert run_command(mio, ["mcp", "list"])[0] == 0
    assert run_command(mio, ["mcp", "status"])[0] == 0
    assert run_command(mio, ["mcp", "doctor"])[0] == 0
    assert run_command(mio, ["mcp", "stats"])[0] == 0
    # install via CLI (JSON kwargs)
    code, out = run_command(mio, ["mcp", "install", "cli-srv", '{"transport":"stdio","trust_level":"trusted"}'])
    assert code == 0 and json.loads(out)["name"] == "cli-srv"
    # list artık 1 gösterir
    assert len(json.loads(run_command(mio, ["mcp", "list"])[1])) == 1
    # geçersiz alt-komut → kullanım
    assert run_command(mio, ["mcp", "uydurma"])[0] == 2
    # rich render (premium metin)
    ui = UI(color=False)
    _c, rich = run_command(mio, ["mcp", "list"], style="rich", ui=ui)
    assert "MCP Servers" in rich


# ---- 8) HTTP entegrasyonu (AYNI appservice DTO — interface eşitliği) ----
def test_mcp_http_endpoints(mio):
    appservice.mcp_register(mio, "http-srv", trust_level="trusted")
    st, data = route_request(mio, "GET", "/mcp", {}, None)
    assert st == 200 and isinstance(data, list) and data[0]["name"] == "http-srv"
    st2, d2 = route_request(mio, "GET", "/mcp/status", {}, None)
    assert st2 == 200 and "stats" in d2
    st3, d3 = route_request(mio, "GET", "/mcp/doctor", {}, None)
    assert st3 == 200 and "servers" in d3
    # CLI dispatch ile HTTP AYNI veriyi verir
    _c, _k, cli_data = dispatch(mio, ["mcp", "list"])
    _s, http_data = route_request(mio, "GET", "/mcp", {}, None)
    assert cli_data == http_data


# ---- 9) persistence: kayıtlı MCP restore edilir ----
def test_mcp_persists_across_reboot(tmp_path):
    ws = str(tmp_path / "mio")
    m1 = boot(workspace=ws, connect_ollama=False, discover_hw=False)
    appservice.mcp_register(m1, "persist-srv", trust_level="trusted")
    m1.close()
    m2 = boot(workspace=ws, connect_ollama=False, discover_hw=False)
    try:
        names = [s["name"] for s in appservice.mcp_list(m2)]
        assert "persist-srv" in names                  # restore("owner") kalıcı kaydı geri yükledi
    finally:
        m2.close()
