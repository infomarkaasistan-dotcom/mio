"""MIO Core · HTTP server lifecycle (CLI'dan) + workspace teşhisi — CLI kalan kalemleri.

Gömülü HTTP API arka-plan thread'inde runtime'ı sunar; CLI start/stop/status. İdempotent, gerçek soket. Workspace
teşhisi salt-okunur. Hepsi appservice'e delege (iş mantığı CLI'da YOK)."""

import json
import urllib.request

import pytest

from mio_core.runtime import boot
from mio_core import appservice
from mio_core.cli import run_command


@pytest.fixture
def mio(tmp_path):
    m = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    yield m
    m.close()


# ---- HTTP server lifecycle ----
def test_server_start_status_stop(mio):
    assert appservice.server_status(mio)["running"] is False
    started = appservice.server_start(mio, host="127.0.0.1", port=0)   # 0 = boş port
    assert started["ok"] and started["status"] == "started" and started["port"] > 0
    port = started["port"]
    assert appservice.server_status(mio)["running"] is True
    # gerçek soket: readiness erişilebilir
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/readiness", timeout=10) as r:
        assert json.load(r)["ready"] is True
    # idempotent: ikinci start → already_running
    assert appservice.server_start(mio, port=0)["status"] == "already_running"
    stopped = appservice.server_stop(mio)
    assert stopped["ok"] and stopped["status"] == "stopped"
    assert appservice.server_status(mio)["running"] is False
    assert appservice.server_stop(mio)["status"] == "not_running"      # idempotent stop


def test_server_via_cli(mio):
    code, out = run_command(mio, ["server", "start", "--port", "0"])
    assert code == 0 and json.loads(out)["ok"]
    assert json.loads(run_command(mio, ["server", "status"])[1])["running"] is True
    assert run_command(mio, ["server", "stop"])[0] == 0
    assert run_command(mio, ["server", "uydurma"])[0] == 2


def test_close_stops_running_server(tmp_path):
    m = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    appservice.server_start(m, port=0)
    assert m.http_server.is_running() is True
    report = m.close()                                # graceful shutdown sunucuyu durdurur
    assert "http_server" in report["closed"] and m.http_server.is_running() is False


# ---- workspace teşhisi ----
def test_workspace_info(mio):
    info = appservice.workspace_info(mio)
    assert info["databases"] > 30 and info["total_bytes"] > 0   # 45 domain db + çekirdek
    assert all(f["name"].endswith(".db") for f in info["files"])
    assert run_command(mio, ["workspace"])[0] == 0
