"""MIO Core · Ops entrypoint (Production Hardening #7) — deployment/monitoring probe KANITI.

`python -m mio_core <cmd>` probe'unun exit kodu + JSON çıktısı doğrulanır (container HEALTHCHECK / readiness /
monitoring scrape). Deterministik; dış adapter gerektirmez."""

import json

import pytest

from mio_core.ops import main, run_probe, _COMMANDS


# ---- run_probe: exit kodu + payload ----
def test_readiness_probe_ready_exit_zero(tmp_path):
    code, payload = run_probe("readiness", workspace=str(tmp_path / "mio"))
    assert code == 0 and payload["ready"] is True
    assert payload["checks"]["domains"]["ready"] == payload["checks"]["domains"]["total"]


def test_health_probe(tmp_path):
    code, payload = run_probe("health", workspace=str(tmp_path / "mio"))
    assert code == 0 and "status" in payload


def test_metrics_probe_aggregates(tmp_path):
    code, payload = run_probe("metrics", workspace=str(tmp_path / "mio"))
    assert code == 0 and payload["domain_count"] == 24
    assert payload["domains"]["iot"]["contract_version"] == "1.0.0"
    assert payload["closed"] is False


def test_unknown_command_exit_two():
    code, payload = run_probe("uydurma", workspace=":skip:")   # boot edilmeden reddedilir
    assert code == 2 and "valid" in payload


def test_commands_catalog():
    assert set(_COMMANDS) == {"readiness", "health", "metrics"}


# ---- main(argv): CLI sözleşmesi (JSON stdout + exit kodu) ----
def test_main_readiness_prints_json_and_returns_zero(tmp_path, capsys):
    rc = main(["readiness", "--workspace", str(tmp_path / "mio")])
    out = capsys.readouterr().out.strip()
    doc = json.loads(out)                          # tek-satır geçerli JSON
    assert rc == 0 and doc["ready"] is True


def test_main_metrics_returns_zero(tmp_path, capsys):
    rc = main(["metrics", "--workspace", str(tmp_path / "mio")])
    doc = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and doc["domain_count"] == 24
