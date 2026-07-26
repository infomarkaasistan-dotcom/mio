"""MIO Core · CLI (Interface Katmanı #1) — terminal arayüzü KANITI.

run_command canlı runtime üzerinde deterministik komutları + reflektif `call`'ı doğrular; main() tek-atış
boot/close sarmalıyla exit kodunu döndürür. __main__ yönlendirmesi (probe→ops, diğer→cli) test edilir."""

import json

import pytest

from mio_core.cli import run_command, main as cli_main
from mio_core.runtime import boot, _READINESS_DOMAINS


@pytest.fixture
def mio(tmp_path):
    m = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    yield m
    m.close()


# ---- inceleme komutları ----
def test_domains_lists_all(mio):
    code, out = run_command(mio, ["domains"])
    assert code == 0
    doc = json.loads(out)
    names = {d["domain"] for d in doc}
    assert len(doc) == len(_READINESS_DOMAINS)
    assert "iot" in names and "extension_sdk" in names
    assert all(d.get("version") == "1.0.0" for d in doc if "version" in d)


def test_contract_and_stats(mio):
    code, out = run_command(mio, ["contract", "iot"])
    assert code == 0 and json.loads(out)["domain"] == "iot"
    code, out = run_command(mio, ["stats", "iot"])
    assert code == 0 and json.loads(out)["contract_version"] == "1.0.0"


def test_metrics_readiness_health(mio):
    assert json.loads(run_command(mio, ["metrics"])[1])["domain_count"] == 24
    rc, out = run_command(mio, ["readiness"])
    assert rc == 0 and json.loads(out)["ready"] is True
    assert run_command(mio, ["health"])[0] == 0


def test_events_returns_list(mio):
    mio.iot.register_thing("owner", "S", kind="sensor")   # bir olay üret
    code, out = run_command(mio, ["events", "5"])
    assert code == 0 and isinstance(json.loads(out), list)


# ---- reflektif call ----
def test_call_invokes_domain_operation(mio):
    code, out = run_command(mio, ["call", "iot", "register_thing",
                                  '{"actor":"owner","name":"Kazan","kind":"sensor"}'])
    assert code == 0
    thing = json.loads(out)
    assert thing["name"] == "Kazan" and thing["kind"] == "sensor" and thing["id"]
    # üretilen id ile ikinci çağrı: telemetri gönder
    code2, out2 = run_command(mio, ["call", "iot", "ingest",
                                    json.dumps({"actor": "owner", "thing_id": thing["id"],
                                                "metric": "temp", "value": 42})])
    assert code2 == 0 and json.loads(out2)["reading"]["value"] == 42.0


def test_call_error_paths(mio):
    assert run_command(mio, ["call", "iot"])[0] == 2                    # eksik operasyon
    assert run_command(mio, ["call", "yok", "x"])[0] == 2               # domain yok
    assert run_command(mio, ["call", "iot", "_private"])[0] == 2        # özel metod
    assert run_command(mio, ["call", "iot", "uydurma_op"])[0] == 2      # operasyon yok
    assert run_command(mio, ["call", "iot", "register_thing", "{bozuk"])[0] == 2  # geçersiz json
    assert run_command(mio, ["call", "iot", "register_thing", "[1,2]"])[0] == 2   # json dict değil
    # yetki hatası → domain fırlatır → CLI 1 + HATA (çökmeden)
    rc, out = run_command(mio, ["call", "iot", "register_thing", '{"actor":"Reasoning","name":"x"}'])
    assert rc == 1 and "HATA" in out and "Unauthorized" in out


def test_connector_commands(mio):
    # connectors/capabilities boş (varsayılan) ama komutlar çalışır
    assert run_command(mio, ["connectors"])[0] == 0
    assert run_command(mio, ["capabilities"])[0] == 0
    # execute: connector yok → çökmez, connector_unavailable (çıkış 0, dürüst sonuç)
    code, out = run_command(mio, ["execute", "send_email", '{"to":"a@b.com"}'])
    assert code == 0 and json.loads(out)["status"] == "connector_unavailable"
    assert run_command(mio, ["execute"])[0] == 2           # eksik capability


def test_unknown_command_and_help(mio):
    assert run_command(mio, ["uydurma"])[0] == 2
    assert run_command(mio, [])[0] == 0
    code, out = run_command(mio, ["help"])
    assert code == 0 and "call" in out and "domains" in out


# ---- one-shot main + __main__ yönlendirme ----
def test_main_oneshot_domains(tmp_path, capsys):
    rc = cli_main(["domains", "--workspace", str(tmp_path / "mio")])
    out = capsys.readouterr().out
    assert rc == 0 and "iot" in out


def test_dunder_main_routes_probe_to_ops(tmp_path, capsys):
    from mio_core.__main__ import main as dispatch
    # readiness → ops probe (exit-kodlu), JSON'da 'ready' anahtarı
    rc = dispatch(["readiness", "--workspace", str(tmp_path / "mio")])
    assert rc == 0 and "ready" in capsys.readouterr().out


def test_dunder_main_routes_other_to_cli(tmp_path, capsys):
    from mio_core.__main__ import main as dispatch
    rc = dispatch(["domains", "--workspace", str(tmp_path / "mio")])
    assert rc == 0 and "extension_sdk" in capsys.readouterr().out
