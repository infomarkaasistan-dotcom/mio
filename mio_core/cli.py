"""MIO Core · CLI — Executive Command Center (Interface Katmanı #1), stdlib-only.

MIO'nun birincil yönetim arayüzü. **Bir kabuk DEĞİL — akıllı bir işletim sisteminin komuta köprüsü.** Sakin,
premium, donanım-farkında, executive-öncelikli. **İş mantığı YOK** (Interface Architecture): her komut
`mio_core.appservice` (paylaşılan Application Service Layer) DTO'sunu alır ve `mio_core.cli_render` ile metne
çevirir. Dashboard/HTTP/Mobile aynı DTO'yu farklı render eder. Backward-compat: `run_command` varsayılan JSON.

Katmanlar:
  dispatch(mio, argv) -> (code, kind, data)   # yalnız appservice'e delege (DTO döndürür; iş mantığı YOK)
  run_command(..., style="json"|"rich")        # DTO'yu JSON ya da premium metne render eder
"""

from __future__ import annotations

import json
import shlex
import sys
from typing import Any, Optional

from mio_core import appservice
from mio_core.appservice import BadRequest, NotFound
from mio_core.cli_render import render
from mio_core.cli_ui import UI

# Kategorili yardım (executive-öncelikli).
_HELP_SECTIONS = [
    ("Executive", [("executive", "operasyonel özet: güven, öneriler, brain/connector durumu"),
                   ("diagnose", "tam sağlık denetimi + Executive Score"),
                   ("readiness / health", "operasyonel hazırlık / sağlık")]),
    ("Domains", [("domains", "43 domain + sözleşme + operasyon sayısı"),
                 ("contract <domain>", "domain public sözleşmesi"),
                 ("stats <domain>", "domain metrikleri"),
                 ("call <domain> <op> [json]", "domain operasyonunu reflektif çağır")]),
    ("Hardware & Models", [("hardware", "CPU/RAM/GPU/VRAM/CUDA/Ollama teşhisi + uyarı"),
                           ("models", "kurulu/yüklü modeller + VRAM'e göre öneri"),
                           ("inference analyze|status|ensure-ready", "yerel çıkarım ortamını yönet")]),
    ("Connectors", [("connect", "env'e göre gerçek connector'ları bağla"),
                    ("connectors", "kayıtlı connector'lar + health"),
                    ("capabilities", "capability → sağlayan connector'lar"),
                    ("execute <cap> [json]", "capability çalıştır (connector yoksa unavailable)")]),
    ("Presentation", [("present list", "sunum senaryoları"),
                      ("present outline <t> <json>", "outline'dan senaryo üret"),
                      ("present plan <id>", "sunum niyet planı (yürütme yok)"),
                      ("present deliver <id> [approve]", "Executive: niyetleri ConnectorManager ile yürüt")]),
    ("Conversation", [("chat queue", "cevap bekleyen mesajlar (öncelik sırası)"),
                      ("chat summary", "konuşma özeti + moderasyon"),
                      ("chat receive <user> <text>", "mesaj al + sınıflandır + moderasyon tespiti"),
                      ("chat reply <id> <text>", "Executive: cevap niyetini yürüt"),
                      ("chat moderate <id> <action>", "Executive: moderasyon niyeti (onay gerektirir)")]),
    ("MCP", [("mcp list", "kayıtlı MCP sunucuları"),
             ("mcp status / doctor", "MCP sağlık / tam teşhis"),
             ("mcp install <name> [json]", "MCP sunucusu kaydet"),
             ("mcp enable", "güvenilir MCP capability'lerini bağla"),
             ("mcp trust <id> <level>", "MCP güven seviyesi (untrusted/trusted/verified)"),
             ("mcp info/remove/discover/stats", "bilgi / kaldır / keşif / metrik")]),
    ("Monitoring", [("metrics", "birleşik metrikler (JSON)"),
                    ("prometheus", "Prometheus text exposition"),
                    ("events [N]", "son N event bus olayı")]),
    ("System", [("config", ".env + os.environ yapılandırma teşhisi (hangi değer nereden)"),
                ("workspace", "workspace teşhisi (yol/boyut/db/disk)"),
                ("server [start|stop|status]", "gömülü HTTP API'yi arka-planda yönet"),
                ("serve [--host --port]", "HTTP API adapter'ını başlat (bloklayan)"),
                ("--json", "herhangi bir komutta ham JSON çıktı zorla"),
                ("help", "bu yardım"), ("quit / exit", "çık")]),
]


def _fmt(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str, sort_keys=True)


def _help_text(ui: Optional[UI]) -> str:
    if ui is None:                                   # JSON/düz mod
        lines = []
        for title, cmds in _HELP_SECTIONS:
            lines.append(title)
            for c, d in cmds:
                lines.append(f"  {c:<34} {d}")
        return "\n".join(lines)
    out = []
    for title, cmds in _HELP_SECTIONS:
        out.append(ui.section(title))
        out.append(ui.kv([(c, d) for c, d in cmds]))
    return "\n".join(out)


# --------------------------------------------------------------------------- #
def dispatch(mio, argv: list) -> tuple[int, str, Any]:
    """Komutu appservice'e delege eder. (exit_code, render_kind, data) döner. İş mantığı YOK.

    render_kind: "text" (data düz metin) · "raw" (JSON) · veya cli_render tipi (domains/hardware/...)."""
    if not argv:
        return 0, "text", ""
    name, rest = argv[0], argv[1:]
    try:
        if name in ("help", "?", "h"):
            return 0, "help", None
        if name == "domains":
            return 0, "domains", appservice.list_domains(mio)
        if name == "executive":
            return 0, "executive", appservice.executive_summary(mio)
        if name == "diagnose":
            d = appservice.diagnose(mio)
            return (0 if d.get("score", 0) >= 50 else 1), "diagnose", d
        if name == "hardware":
            return 0, "hardware", appservice.hardware_report(mio)
        if name == "models":
            return 0, "models", appservice.models_overview(mio)
        if name == "connectors":
            return 0, "connectors", appservice.connectors_overview(mio)
        if name == "capabilities":
            return 0, "capabilities", appservice.capabilities_catalog(mio)
        if name == "metrics":
            return 0, "raw", appservice.metrics(mio)
        if name == "prometheus":
            return 0, "text", appservice.prometheus_metrics(mio)
        if name == "readiness":
            r = appservice.readiness(mio)
            return (0 if r.get("ready") else 1), "raw", r
        if name == "health":
            return 0, "raw", appservice.health(mio)
        if name == "events":
            limit = int(rest[0]) if rest and rest[0].isdigit() else 20
            return 0, "raw", appservice.events(mio, limit)
        if name == "contract":
            if not rest:
                return 2, "text", "kullanım: contract <domain>"
            return 0, "raw", appservice.domain_contract(mio, rest[0])
        if name == "stats":
            if not rest:
                return 2, "text", "kullanım: stats <domain>"
            return 0, "raw", appservice.domain_stats(mio, rest[0])
        if name == "call":
            return _do_call(mio, rest)
        if name == "execute":
            return _do_execute(mio, rest)
        if name == "inference":
            return _do_inference(mio, rest)
        if name == "mcp":
            return _do_mcp(mio, rest)
        if name in ("present", "presentation"):
            return _do_present(mio, rest)
        if name in ("chat", "conversation", "conv"):
            return _do_chat(mio, rest)
        if name == "connect":
            return 0, "raw", appservice.connect_env(mio)
        if name == "config":
            return 0, "raw", appservice.config_diagnostics(mio)
        if name == "workspace":
            return 0, "raw", appservice.workspace_info(mio)
        if name == "server":                          # gömülü HTTP API'yi CLI'dan yönet (arka-plan)
            sub = rest[0] if rest else "status"
            if sub == "start":
                host = _pop_flag(rest, "--host") or "127.0.0.1"
                port = _pop_flag(rest, "--port") or "8080"
                return 0, "raw", appservice.server_start(mio, host=host, port=int(port))
            if sub == "stop":
                return 0, "raw", appservice.server_stop(mio)
            if sub == "status":
                return 0, "raw", appservice.server_status(mio)
            return 2, "text", "kullanım: server [start [--host --port] | stop | status]"
        return 2, "text", f"bilinmeyen komut: {name}  ('help' ile komut listesi)"
    except (NotFound, BadRequest) as exc:
        return 2, "text", f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 — domain istisnası (authz/validation) → 1; süreci çökertmez
        return 1, "text", f"HATA: {type(exc).__name__}: {exc}"


def _do_call(mio, rest: list) -> tuple[int, str, Any]:
    if len(rest) < 2:
        return 2, "text", 'kullanım: call <domain> <op> [json]  ör: call iot register_thing {"actor":"owner","name":"S"}'
    kwargs = _parse_json_arg(rest[2:])
    if isinstance(kwargs, str):
        return 2, "text", kwargs
    return 0, "raw", appservice.call(mio, rest[0], rest[1], kwargs)


def _do_execute(mio, rest: list) -> tuple[int, str, Any]:
    if not rest:
        return 2, "text", 'kullanım: execute <capability> [json]  ör: execute send_email {"to":"a@b.com"}'
    request = _parse_json_arg(rest[1:])
    if isinstance(request, str):
        return 2, "text", request
    return 0, "capability_exec", appservice.execute_capability(mio, rest[0], request)


def _do_inference(mio, rest: list) -> tuple[int, str, Any]:
    sub = rest[0] if rest else "analyze"
    if sub == "analyze":
        return 0, "raw", appservice.inference_analyze(mio)
    if sub == "status":
        return 0, "raw", (mio.inference_status or {"prepared": False,
                          "note": "otomatik hazırlık kapalı — 'inference ensure-ready' çalıştırın"})
    if sub in ("ensure-ready", "ensure", "prepare"):
        rep = appservice.inference_ensure_ready(mio, approve=set(rest[1:]))
        return (0 if rep.get("ready") else 1), "inference_ensure", rep
    return 2, "text", "kullanım: inference [analyze | status | ensure-ready [onay...]]"


def _do_mcp(mio, rest: list) -> tuple[int, str, Any]:
    """MCP Manager alt-komutları — hepsi appservice'e delege (iş mantığı mcp_management domaininde)."""
    sub = rest[0] if rest else "list"
    args = rest[1:]
    if sub in ("list", "ls"):
        return 0, "mcp_list", appservice.mcp_list(mio)
    if sub in ("status", "health"):
        return 0, "mcp_status", appservice.mcp_status(mio)
    if sub in ("doctor", "diagnose"):
        return 0, "mcp_doctor", appservice.mcp_doctor(mio)
    if sub == "discover":
        return 0, "raw", appservice.mcp_discover(mio)
    if sub == "stats":
        return 0, "raw", appservice.mcp_stats(mio)
    if sub == "capabilities":
        return 0, "raw", appservice.mcp_contract(mio)
    if sub in ("info", "describe", "config"):
        if not args:
            return 2, "text", f"kullanım: mcp {sub} <server_id>"
        return 0, "raw", appservice.mcp_info(mio, args[0])
    if sub in ("install", "register", "add"):
        if not args:
            return 2, "text", 'kullanım: mcp install <name> [json]  ör: mcp install fs {"transport":"stdio","command":"npx ..."}'
        kwargs = _parse_json_arg(args[1:])
        if isinstance(kwargs, str):
            return 2, "text", kwargs
        return 0, "raw", appservice.mcp_register(mio, args[0], **kwargs)
    if sub in ("uninstall", "remove", "rm"):
        if not args:
            return 2, "text", "kullanım: mcp remove <server_id>"
        return 0, "raw", appservice.mcp_remove(mio, args[0])
    if sub in ("enable", "activate"):
        return 0, "raw", appservice.mcp_activate(mio)
    if sub == "trust":
        if len(args) < 2:
            return 2, "text", "kullanım: mcp trust <server_id> <untrusted|trusted|verified>"
        return 0, "raw", appservice.mcp_trust(mio, args[0], args[1])
    return 2, "text", ("kullanım: mcp [list | status | doctor | discover | stats | capabilities | "
                       "info <id> | install <name> [json] | remove <id> | enable | trust <id> <level>]")


def _do_present(mio, rest: list) -> tuple[int, str, Any]:
    """Presentation alt-komutları — appservice'e delege. deliver = Executive köprüsü (niyetleri yürütür)."""
    sub = rest[0] if rest else "list"
    args = rest[1:]
    if sub in ("list", "ls"):
        return 0, "raw", appservice.presentation_list(mio)
    if sub == "plan":
        if not args:
            return 2, "text", "kullanım: present plan <script_id>"
        return 0, "raw", appservice.presentation_plan(mio, args[0])
    if sub == "deliver":
        if not args:
            return 2, "text", "kullanım: present deliver <script_id> [approve]"
        approve = len(args) > 1 and args[1].lower() in ("approve", "yes", "1", "true")
        return 0, "raw", appservice.presentation_deliver(mio, args[0], approve=approve)
    if sub == "outline":
        if len(args) < 2:
            return 2, "text", 'kullanım: present outline <title> <json-liste>  ör: present outline "Sunum" ["A","B"]'
        try:
            parsed = json.loads(" ".join(args[1:]))
        except json.JSONDecodeError as exc:
            return 2, "text", f"geçersiz JSON: {exc}"
        items = parsed if isinstance(parsed, list) else (parsed.get("outline", []) if isinstance(parsed, dict) else [])
        return 0, "raw", appservice.presentation_outline(mio, args[0], items)
    return 2, "text", "kullanım: present [list | plan <id> | deliver <id> [approve] | outline <title> <json>]"


def _do_chat(mio, rest: list) -> tuple[int, str, Any]:
    """Conversation alt-komutları — appservice'e delege. reply/moderate = Executive köprüsü (niyeti yürütür)."""
    sub = rest[0] if rest else "queue"
    args = rest[1:]
    if sub == "queue":
        return 0, "raw", appservice.conversation_queue(mio)
    if sub == "summary":
        return 0, "raw", appservice.conversation_summary(mio)
    if sub == "receive":
        if len(args) < 2:
            return 2, "text", "kullanım: chat receive <user> <text...>"
        return 0, "raw", appservice.conversation_receive(mio, args[0], " ".join(args[1:]))
    if sub == "reply":
        if len(args) < 2:
            return 2, "text", "kullanım: chat reply <message_id> <text...>"
        return 0, "raw", appservice.conversation_reply(mio, args[0], " ".join(args[1:]))
    if sub in ("moderate", "mod"):
        if len(args) < 2:
            return 2, "text", "kullanım: chat moderate <message_id> <delete|timeout|ban|pin> [approve]"
        approve = len(args) > 2 and args[2].lower() in ("approve", "yes", "1", "true")
        return 0, "raw", appservice.conversation_moderate(mio, args[0], args[1], approve=approve)
    return 2, "text", "kullanım: chat [queue | summary | receive <user> <text> | reply <id> <text> | moderate <id> <action>]"


def _parse_json_arg(parts: list):
    """JSON argümanını dict'e çevirir; hata → açıklama metni (str). Boş → {}."""
    raw = " ".join(parts).strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return f"geçersiz JSON: {exc}"
    if not isinstance(parsed, dict):
        return 'JSON bir nesne olmalı, ör: {"actor":"owner"}'
    return parsed


# --------------------------------------------------------------------------- #
def run_command(mio, argv: list, *, style: str = "json", ui: Optional[UI] = None) -> tuple[int, str]:
    """dispatch + render. Backward-compat: style='json' (varsayılan) → mevcut davranış (DTO'lar JSON).
    style='rich' + ui → premium metin. `--json` argümanı style'ı json'a zorlar."""
    argv = list(argv)
    if "--json" in argv:
        argv.remove("--json")
        style = "json"
    code, kind, data = dispatch(mio, argv)
    if kind == "help":
        return code, _help_text(ui if style == "rich" else None)
    if kind == "text":
        return code, data if isinstance(data, str) else _fmt(data)
    if style == "rich" and ui is not None:
        return code, render(kind, ui, data)
    return code, _fmt(data)


# --------------------------------------------------------------------------- #
def startup_sequence(mio, ui: UI, *, workspace: str) -> None:
    """Executive Startup Sequence — banner + boot adımları + donanım farkındalığı. Sakin, bilgilendirici."""
    ver = "0.1.0-alpha"
    mode = "Autonomous" if (mio.inference_status or {}).get("ready") else "Deterministic"
    ui.out(ui.banner(version=ver, workspace=workspace, mode=mode))
    ui.out(ui.rule("Executive Boot Sequence"))
    for label in ("Executive", "Memory", "Knowledge", "Event Bus", "Connector Manager",
                  "Persistence", "Brains", "Scheduler", "Monitoring", "Runtime"):
        ui.out(ui.boot_step(label, ok=True))
    ui.out(ui.rule())
    # Donanım + LLM farkındalığı (kısa, executive özet — config'ten LLM durumu)
    try:
        hw = appservice.hardware_report(mio)
        g = hw["gpus"][0] if hw.get("gpus") else None
        ol = hw.get("ollama", {})
        llm_on = mio.config.get_bool("LLM_ENABLED", False)
        fields = [("GPU", g["name"].replace("NVIDIA GeForce ", "") if g else "none", "ok" if g else "warn"),
                  ("VRAM", f"{g['memory_free_mb']}MB" if g else "-", "ok" if g else "mute"),
                  ("CUDA", hw.get("cuda", {}).get("version") or "no", "ok" if hw.get("cuda", {}).get("available") else "warn"),
                  ("LLM", "enabled" if llm_on else "disabled", "ok" if llm_on else "mute"),
                  ("Ollama", "detected" if ol.get("reachable") else "off", "ok" if ol.get("reachable") else "mute")]
        ui.out(ui.statusline(fields))
        models = ol.get("loaded_models", [])
        installed = mio.local_inference.installed_models() if ol.get("reachable") else []
        if installed:
            ui.out(ui.note(f"Installed models: {', '.join(installed[:5])}"
                           + (f" (+{len(installed) - 5})" if len(installed) > 5 else ""), "info"))
        for w in hw.get("warnings", [])[:2]:
            ui.out(ui.note(w, "warn"))
    except Exception:  # noqa: BLE001 — donanım özeti başarısızsa startup'ı bozmaz
        pass
    ui.out(ui.rule())
    ui.out("  " + ui.badge("Executive Ready", "ok"))
    ui.out("")


def interactive(mio, *, workspace: str = ".mio") -> int:
    """Premium etkileşimli REPL (gerçek terminal). MIO ❯ prompt + rich render + startup sequence."""
    ui = UI()
    startup_sequence(mio, ui, workspace=workspace)
    prompt = ui.prompt()
    while True:
        try:
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            ui.out("")
            return 0
        if not line:
            continue
        if line in ("quit", "exit", "q"):
            ui.out(ui.note("Executive kapanıyor.", "mute"))
            return 0
        try:
            argv = shlex.split(line)
        except ValueError as exc:
            ui.out(ui.note(f"ayrıştırma hatası: {exc}", "err"))
            continue
        _code, out = run_command(mio, argv, style="rich", ui=ui)
        if out:
            ui.out(out)


def _pop_flag(argv: list, flag: str) -> Optional[str]:
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            val = argv[i + 1]
            del argv[i:i + 2]
            return val
    return None


def main(argv: Optional[list] = None) -> int:
    import os
    argv = list(sys.argv[1:] if argv is None else argv)
    workspace = _pop_flag(argv, "--workspace") or os.environ.get("MIO_WORKSPACE", ".mio")
    host = _pop_flag(argv, "--host") or os.environ.get("MIO_HTTP_HOST", "127.0.0.1")
    port = _pop_flag(argv, "--port") or os.environ.get("MIO_HTTP_PORT", "8080")
    force_json = "--json" in argv
    is_interactive = (not [a for a in argv if a != "--json"]) or argv[0] == "shell"

    from mio_core.runtime import boot
    mio = boot(workspace=workspace, connect_ollama=False, discover_hw=False)
    try:
        if is_interactive and not force_json:
            return interactive(mio, workspace=workspace)
        if argv and argv[0] in ("serve", "http"):
            from mio_core.http_api import serve
            serve(mio, host=host, port=int(port))
            return 0
        # tek-atış: TTY ise rich, değilse (pipe/redirect) ya da --json ise JSON
        ui = UI()
        style = "json" if (force_json or not sys.stdout.isatty()) else "rich"
        code, out = run_command(mio, argv, style=style, ui=ui)
        if out:
            print(out)
        return code
    finally:
        mio.close()


if __name__ == "__main__":
    sys.exit(main())
