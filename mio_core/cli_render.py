"""MIO Core · CLI render — Application Service DTO'larını premium metne çevirir (SADECE SUNUM).

Her komut tipi için bir renderer: `render(kind, ui, data) -> str`. İş mantığı YOK (DTO'lar appservice'ten gelir).
Bilinmeyen kind → JSON'a düşer (güvenli). `--json` istenirse hiç çağrılmaz (ham JSON verilir)."""

from __future__ import annotations

import json
from typing import Any

from mio_core.cli_ui import UI


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str, sort_keys=True)


# --------------------------------------------------------------------------- #
def _r_domains(ui: UI, data: list) -> str:
    rows = [[d.get("domain", ""), d.get("version", ""), str(d.get("operations", "")),
             (d.get("description", "") or "")[:56]] for d in data]
    return (ui.section(f"Domains  ({len(data)})") + "\n"
            + ui.table(["DOMAIN", "VER", "OPS", "DESCRIPTION"], rows))


def _r_hardware(ui: UI, d: dict) -> str:
    cpu, ram, cuda = d.get("cpu", {}), d.get("ram", {}), d.get("cuda", {})
    gpus, ol = d.get("gpus", []), d.get("ollama", {})
    lines = [ui.section("Hardware")]
    kv = [("CPU", f"{cpu.get('cores', '?')} cores · {(cpu.get('name') or '')[:40]}"),
          ("RAM", f"{ram.get('available_mb', 0)} / {ram.get('total_mb', 0)} MB free")]
    if gpus:
        g = gpus[0]
        kv.append(("GPU", f"{g.get('name')} · {g.get('memory_free_mb', 0)}/{g.get('memory_total_mb', 0)} MB VRAM"))
        kv.append(("CUDA", ("✓ " + str(cuda.get("version"))) if cuda.get("available") else "not detected"))
    else:
        kv.append(("GPU", "not detected"))
    kv.append(("Ollama", (f"running · v{ol.get('version')}" if ol.get("reachable") else "not running")))
    out = [lines[0], ui.kv(kv)]
    loaded = ol.get("loaded_models", [])
    if loaded:
        rows = [[m.get("name"), m.get("placement"), f"{m.get('size_vram_gb', 0)}/{m.get('size_gb', 0)} GB"]
                for m in loaded]
        out += ["", ui.table(["LOADED MODEL", "DEVICE", "VRAM/SIZE"], rows)]
    for w in d.get("warnings", []):
        out.append(ui.note(w, "warn"))
    for r in d.get("recommendations", []):
        out.append(ui.note(r, "info"))
    return "\n".join(out)


def _r_connectors(ui: UI, data: list) -> str:
    if not data:
        return ui.section("Connectors") + "\n" + ui.note("Hiç connector bağlı değil — 'connect' ile bağla.", "mute")
    rows = []
    for c in data:
        h = c.get("health", {})
        dot = ui.status_dot(h.get("ok", True))
        rows.append([dot + " " + str(c.get("name")), c.get("category", ""),
                     str(len(c.get("capabilities", []))), str(c.get("priority", ""))])
    return (ui.section(f"Connectors  ({len(data)})") + "\n"
            + ui.table(["NAME", "CATEGORY", "CAPS", "PRIORITY"], rows))


def _r_capabilities(ui: UI, d: dict) -> str:
    caps = d.get("capabilities", {})
    if not caps:
        return ui.section("Capabilities") + "\n" + ui.note("Kayıtlı capability yok.", "mute")
    rows = [[cap, ", ".join(provs)] for cap, provs in sorted(caps.items())]
    return ui.section(f"Capabilities  ({len(caps)})") + "\n" + ui.table(["CAPABILITY", "PROVIDERS"], rows)


def _r_models(ui: UI, d: dict) -> str:
    out = [ui.section("Models")]
    out.append(ui.kv([("Ollama", "running" if d.get("ollama_reachable") else "not running"),
                      ("Recommended", d.get("recommended") or "—"),
                      ("VRAM free", f"{d.get('vram_free_mb', 0)} MB")]))
    cand = d.get("candidates", [])
    if cand:
        rows = [[c.get("model"), f"{c.get('params_b') or '?'}B",
                 "GPU ✓" if c.get("fits_gpu") else "CPU only", f"{c.get('vram_need_mb', 0)} MB"]
                for c in cand]
        out += ["", ui.table(["MODEL", "PARAMS", "FITS", "VRAM NEED"], rows)]
    loaded = d.get("loaded", [])
    if loaded:
        rows = [[m.get("name"), m.get("placement"), f"{m.get('size_vram_gb', 0)} GB"] for m in loaded]
        out += ["", ui.table(["RUNNING", "DEVICE", "VRAM"], rows)]
    return "\n".join(out)


def _r_diagnose(ui: UI, d: dict) -> str:
    out = [ui.section("Diagnostics")]
    rows = [[ui.status_dot(c["status"]) + " " + c["component"], c.get("detail", "")]
            for c in d.get("components", [])]
    out.append(ui.table(["COMPONENT", "DETAIL"], rows))
    for w in d.get("warnings", []):
        out.append(ui.note(w, "warn"))
    for r in d.get("recommendations", []):
        out.append(ui.note(r, "info"))
    out += ["", "  " + ui.score(d.get("score", 0), d.get("max", 100)) + "   " + ui.badge(d.get("verdict", ""),
            "ok" if d.get("score", 0) >= 80 else "warn")]
    return "\n".join(out)


def _r_executive(ui: UI, d: dict) -> str:
    idn = d.get("identity", {})
    inf = d.get("inference", {})
    out = [ui.section(f"Executive · {idn.get('name', 'MIO')}")]
    out.append(ui.kv([
        ("System Confidence", ui.badge(d.get("system_confidence", ""),
                                       "ok" if d.get("executive_score", 0) >= 80 else "warn")),
        ("Executive Score", f"{d.get('executive_score', 0)}/100"),
        ("Domains", d.get("domains", 0)),
        ("Brains", d.get("brains", 0)),
        ("Connectors", d.get("connectors", 0)),
        ("Inference", (f"{inf.get('model')} (ready)" if inf.get("prepared") else "hazır değil")),
    ]))
    if d.get("recommended_actions"):
        out.append("")
        for a in d["recommended_actions"]:
            out.append(ui.note(a, "info"))
    for w in d.get("warnings", []):
        out.append(ui.note(w, "warn"))
    return "\n".join(out)


def _r_inference_ensure(ui: UI, d: dict) -> str:
    out = [ui.section("Inference · Ensure Ready")]
    out.append(ui.kv([("Selected model", d.get("selected_model") or "—"),
                      ("Ready", "✓" if d.get("ready") else "✕")]))
    for a in d.get("actions_executed", []):
        out.append(ui.note(f"{a.get('action')} {a.get('model', '')} → {'ok' if a.get('ok') else 'fail'}",
                           "ok" if a.get("ok") else "warn"))
    for p in d.get("pending_approval", []):
        out.append(ui.note(f"onay bekliyor: {p.get('action')} {p.get('model', '')}", "warn"))
    for w in d.get("warnings", []):
        out.append(ui.note(w, "warn"))
    if d.get("message"):
        out.append(ui.note(d["message"], "ok" if d.get("ready") else "info"))
    return "\n".join(out)


def _r_capability_exec(ui: UI, d: dict) -> str:
    status = d.get("status", "")
    kind = {"executed": "ok", "connector_unavailable": "warn", "requires_approval": "warn",
            "failed": "err"}.get(status, "mute")
    out = [ui.note(f"{d.get('capability')} → {status}", kind)]
    if d.get("connector"):
        out.append(ui.kv([("connector", d["connector"])]))
    if d.get("result") is not None:
        out.append(ui.kv([("result", json.dumps(d["result"], ensure_ascii=False)[:200])]))
    if d.get("message"):
        out.append(ui.note(d["message"], kind))
    return "\n".join(out)


def _r_mcp_list(ui: UI, data: list) -> str:
    if not data:
        return (ui.section("MCP Servers") + "\n"
                + ui.note("Kayıtlı MCP sunucusu yok — 'mcp install <name>' ile ekle.", "mute"))
    rows = []
    for s in data:
        dot = ui.status_dot(s.get("status") in ("healthy", "active", "connected") or s.get("healthy"))
        rows.append([dot + " " + str(s.get("name", s.get("id", "?"))), s.get("trust_level", s.get("trust", "")),
                     s.get("status", ""), str(len(s.get("capabilities", [])))])
    return ui.section(f"MCP Servers  ({len(data)})") + "\n" + ui.table(["NAME", "TRUST", "STATUS", "CAPS"], rows)


def _r_mcp_status(ui: UI, d: dict) -> str:
    st = d.get("stats", {})
    out = [ui.section("MCP Status")]
    out.append(ui.kv([("Servers", st.get("servers", 0)), ("Healthy", st.get("healthy", 0)),
                      ("Trusted", st.get("by_trust", {}).get("trusted", 0)),
                      ("Verified", st.get("by_trust", {}).get("verified", 0)),
                      ("Activations", st.get("activations", 0))]))
    health = d.get("health", {})
    if health:
        rows = [[k, ("✓" if (v.get("ok") if isinstance(v, dict) else v) else "✕")] for k, v in health.items()]
        out += ["", ui.table(["SERVER", "HEALTH"], rows)]
    else:
        out.append(ui.note("Aktif MCP sunucusu yok (dürüst boş durum).", "mute"))
    return "\n".join(out)


def _r_mcp_doctor(ui: UI, d: dict) -> str:
    out = [_r_mcp_list(ui, d.get("servers", [])), _r_mcp_status(ui, {"health": d.get("health", {}),
                                                                     "stats": d.get("stats", {})})]
    disc = d.get("discovery", {})
    if disc:
        out.append(ui.note(f"discovery: {json.dumps(disc, ensure_ascii=False)[:120]}", "info"))
    return "\n".join(out)


_RENDERERS = {
    "domains": _r_domains, "hardware": _r_hardware, "connectors": _r_connectors,
    "capabilities": _r_capabilities, "models": _r_models, "diagnose": _r_diagnose,
    "executive": _r_executive, "inference_ensure": _r_inference_ensure,
    "capability_exec": _r_capability_exec,
    "mcp_list": _r_mcp_list, "mcp_status": _r_mcp_status, "mcp_doctor": _r_mcp_doctor,
}


def render(kind: str, ui: UI, data: Any) -> str:
    """DTO → premium metin. Bilinmeyen kind → JSON (güvenli düşüş)."""
    fn = _RENDERERS.get(kind)
    if fn is None:
        return _json(data)
    try:
        return fn(ui, data)
    except Exception:  # noqa: BLE001 — render hatası asla veriyi gizlemesin → JSON'a düş
        return _json(data)


__all__ = ["render"]
