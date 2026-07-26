"""MIO Core · CLI sunum katmanı (cli_ui + cli_render) + yeni komutlar — KANIT.

Sunum SADECE render (iş mantığı yok). Renk/no-color, ASCII fallback, tablo/section/score, rich render, --json
zorlaması, startup sequence, yeni komutlar (executive/diagnose/models), backward-compat run_command doğrulanır."""

import io
import json

import pytest

from mio_core.cli_ui import UI
from mio_core.cli_render import render


# ---- UI: renk kontrolü + ASCII fallback ----
def test_ui_color_toggle_and_nocolor(monkeypatch):
    buf = io.StringIO()
    ui = UI(color=True, stream=buf)
    assert "\033[" in ui.section("X")                 # renk açık → ANSI kodu
    ui2 = UI(color=False, stream=buf)
    assert "\033[" not in ui2.section("X")             # renk kapalı → düz


def test_ui_table_and_score():
    ui = UI(color=False, stream=io.StringIO())
    t = ui.table(["A", "B"], [["1", "22"], ["333", "4"]])
    assert "A" in t and "333" in t and "─" in t
    s = ui.score(100, 100)
    assert "100/100" in s


def test_ui_ascii_fallback_on_legacy_encoding():
    class _Legacy(io.StringIO):
        encoding = "cp1254"
    buf = _Legacy()
    ui = UI(color=False, stream=buf)
    ui.out("─●❯")                                      # Unicode → cp1254 encode edilemez → ASCII'ye çevrilir
    val = buf.getvalue()
    assert "-" in val and "*" in val and ">" in val and "─" not in val


# ---- render: DTO → metin (bilinmeyen kind → JSON) ----
def test_render_known_and_unknown_kinds():
    ui = UI(color=False, stream=io.StringIO())
    diag = {"score": 90, "max": 100, "verdict": "System Ready",
            "components": [{"component": "Executive Core", "status": "ok", "detail": "açık"}],
            "warnings": [], "recommendations": []}
    out = render("diagnose", ui, diag)
    assert "Diagnostics" in out and "Executive Core" in out and "90/100" in out
    # bilinmeyen kind → JSON (güvenli düşüş)
    assert json.loads(render("uydurma_kind", ui, {"x": 1}))["x"] == 1


def test_render_never_hides_data_on_error():
    ui = UI(color=False, stream=io.StringIO())
    # tip-uyumsuz DTO (domains list bekler, dict verildi) → render exception yerine JSON'a düşer (veri gizlenmez)
    out = render("domains", ui, {"unexpected": True})
    assert "unexpected" in out


# ---- backward-compat: run_command style='json' (varsayılan) ----
def test_run_command_json_default(tmp_path):
    from mio_core.runtime import boot
    from mio_core.cli import run_command
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        code, out = run_command(mio, ["domains"])      # varsayılan JSON (mevcut testler bunu bekler)
        assert code == 0 and isinstance(json.loads(out), list)
        # --json her yerde JSON zorlar (rich istense bile)
        ui = UI(color=False, stream=io.StringIO())
        code2, out2 = run_command(mio, ["diagnose", "--json"], style="rich", ui=ui)
        assert json.loads(out2)["score"] >= 0
    finally:
        mio.close()


# ---- rich mod: yeni komutlar premium metin döner ----
def test_rich_new_commands(tmp_path):
    from mio_core.runtime import boot
    from mio_core.cli import run_command
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    ui = UI(color=False, stream=io.StringIO())
    try:
        for cmd, marker in [(["executive"], "Executive"), (["diagnose"], "Diagnostics"),
                            (["models"], "Models"), (["hardware"], "Hardware")]:
            code, out = run_command(mio, cmd, style="rich", ui=ui)
            assert code in (0, 1) and marker in out
    finally:
        mio.close()


# ---- startup sequence çökmez + Executive Ready ----
def test_startup_sequence_renders(tmp_path):
    from mio_core.runtime import boot
    from mio_core.cli import startup_sequence
    buf = io.StringIO()
    ui = UI(color=False, stream=buf)
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        startup_sequence(mio, ui, workspace=str(tmp_path / "mio"))
        val = buf.getvalue()
        assert "MIO Executive OS" in val and "Executive Boot Sequence" in val and "Executive Ready" in val
    finally:
        mio.close()


# ---- help kategorili ----
def test_help_is_categorized(tmp_path):
    from mio_core.runtime import boot
    from mio_core.cli import run_command
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    ui = UI(color=False, stream=io.StringIO())
    try:
        _c, out = run_command(mio, ["help"], style="rich", ui=ui)
        assert "Executive" in out and "Connectors" in out and "diagnose" in out
    finally:
        mio.close()
