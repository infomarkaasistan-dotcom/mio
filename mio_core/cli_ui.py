"""MIO Core · CLI sunum katmanı — premium, sakin, minimal terminal render (stdlib ANSI).

**SADECE SUNUM** (iş mantığı YOK). Application Service DTO'larını metne çevirir; Dashboard aynı DTO'yu karta
çevirecek (Interface Architecture). TTY + NO_COLOR + --no-color farkında; renk paleti minimaldir (rainbow yok,
hacker estetiği yok) — bilgi taşımayan hiçbir süs yoktur. Apple/Linear/Raycast hissi."""

from __future__ import annotations

import os
import shutil
import sys
from typing import Any, Iterable, Optional


class Theme:
    """Minimal, anlam-taşıyan palet (256-color; her rengin işlevi var)."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ACCENT = "\033[38;5;39m"      # executive/başlık — sakin mavi
    OK = "\033[38;5;42m"          # sağlıklı — yeşil
    WARN = "\033[38;5;214m"       # uyarı — amber
    ERR = "\033[38;5;203m"        # hata — mercan kırmızı
    MUTE = "\033[38;5;245m"       # ikincil — gri
    LABEL = "\033[38;5;110m"      # etiket — soluk mavi-gri


# Unicode glyph → ASCII (encode edilemeyen terminaller için, ör. Windows cp1254)
_ASCII_MAP = {"─": "-", "●": "*", "❯": ">", "█": "#", "░": ".", "✓": "+", "✕": "x", "›": ">", "·": "|"}


class UI:
    def __init__(self, *, color: Optional[bool] = None, stream=None) -> None:
        self._out = stream or sys.stdout
        # Windows/legacy konsollarda UTF-8'e geç (box-drawing için); olmazsa out() ASCII'ye düşer.
        try:
            enc = (getattr(self._out, "encoding", "") or "").lower()
            if hasattr(self._out, "reconfigure") and enc not in ("utf-8", "utf8"):
                self._out.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 — reconfigure yoksa sorun değil (ASCII fallback devrede)
            pass
        if color is None:
            color = (self._out.isatty() and os.environ.get("NO_COLOR") is None
                     and os.environ.get("TERM") != "dumb")
        self.color = bool(color)

    # -- düşük seviye -- #
    def _c(self, text: str, *codes: str) -> str:
        if not self.color or not codes:
            return text
        return "".join(codes) + text + Theme.RESET

    def width(self) -> int:
        return shutil.get_terminal_size((100, 24)).columns

    def out(self, text: str = "") -> None:
        line = text + "\n"
        enc = (getattr(self._out, "encoding", "") or "utf-8")
        try:
            line.encode(enc)
        except (UnicodeEncodeError, LookupError):     # terminal Unicode yazamıyor → ASCII'ye çevir (çökme yok)
            for u, a in _ASCII_MAP.items():
                line = line.replace(u, a)
        self._out.write(line)

    # -- bileşenler -- #
    def rule(self, label: str = "") -> str:
        w = min(self.width(), 100)
        if not label:
            return self._c("─" * w, Theme.MUTE)
        line = f"─── {label} " + "─" * max(0, w - len(label) - 5)
        return self._c(line, Theme.MUTE)

    def banner(self, *, version: str, workspace: str, mode: str) -> str:
        a = lambda t: self._c(t, Theme.ACCENT, Theme.BOLD)  # noqa: E731
        m = lambda t: self._c(t, Theme.MUTE)                # noqa: E731
        lines = [
            "",
            a("  MIO Executive OS"),
            m("  Multi-Brain Intelligence Operating System"),
            "",
            f"  {m('Version')}    {version}",
            f"  {m('Workspace')}  {workspace}",
            f"  {m('Mode')}       {mode}",
            "",
        ]
        return "\n".join(lines)

    def section(self, title: str) -> str:
        return "\n" + self._c(f"  {title}", Theme.ACCENT, Theme.BOLD)

    def kv(self, pairs: Iterable[tuple], *, indent: int = 2) -> str:
        pairs = list(pairs)
        wlab = max((len(str(k)) for k, _ in pairs), default=0)
        rows = []
        for k, v in pairs:
            label = self._c(str(k).ljust(wlab), Theme.LABEL)
            rows.append(" " * indent + f"{label}   {v}")
        return "\n".join(rows)

    def status_dot(self, ok: Any) -> str:
        if ok is True or ok == "ok":
            return self._c("●", Theme.OK)
        if ok is False or ok in ("attention", "error"):
            return self._c("●", Theme.ERR)
        return self._c("●", Theme.WARN)

    def badge(self, text: str, kind: str = "mute") -> str:
        code = {"ok": Theme.OK, "warn": Theme.WARN, "err": Theme.ERR,
                "accent": Theme.ACCENT}.get(kind, Theme.MUTE)
        return self._c(text, code)

    def table(self, headers: list, rows: list, *, indent: int = 2) -> str:
        cols = len(headers)
        widths = [len(str(h)) for h in headers]
        srows = [[("" if c is None else str(c)) for c in r] for r in rows]
        for r in srows:
            for i in range(cols):
                widths[i] = max(widths[i], len(r[i]) if i < len(r) else 0)
        pad = " " * indent
        head = pad + "  ".join(self._c(str(headers[i]).ljust(widths[i]), Theme.MUTE, Theme.BOLD)
                                for i in range(cols))
        sep = pad + "  ".join(self._c("─" * widths[i], Theme.MUTE) for i in range(cols))
        body = []
        for r in srows:
            body.append(pad + "  ".join((r[i] if i < len(r) else "").ljust(widths[i]) for i in range(cols)))
        return "\n".join([head, sep, *body])

    def note(self, text: str, kind: str = "mute") -> str:
        glyph = {"ok": "✓", "warn": "!", "err": "✕", "info": "›"}.get(kind, "›")
        code = {"ok": Theme.OK, "warn": Theme.WARN, "err": Theme.ERR}.get(kind, Theme.MUTE)
        return "  " + self._c(f"{glyph} {text}", code)

    def score(self, value: int, maximum: int = 100) -> str:
        filled = round(12 * value / max(1, maximum))
        kind = Theme.OK if value >= 80 else (Theme.WARN if value >= 50 else Theme.ERR)
        bar = self._c("█" * filled, kind) + self._c("░" * (12 - filled), Theme.MUTE)
        return f"{bar}  {self._c(str(value) + '/' + str(maximum), kind, Theme.BOLD)}"

    # -- startup / progress -- #
    def boot_step(self, label: str, ok: bool = True) -> str:
        return "  " + self.status_dot(ok) + " " + self._c(label, Theme.MUTE)

    def statusline(self, fields: list) -> str:
        """Kalıcı durum satırı: [(label, value, kind)] → tek satır, ayraçlı."""
        parts = []
        for label, value, *rest in fields:
            kind = rest[0] if rest else "mute"
            code = {"ok": Theme.OK, "warn": Theme.WARN, "err": Theme.ERR,
                    "accent": Theme.ACCENT}.get(kind, Theme.MUTE)
            parts.append(self._c(str(label), Theme.MUTE) + " " + self._c(str(value), code))
        return "  " + self._c(" · ", Theme.MUTE).join(parts)

    def prompt(self) -> str:
        return self._c("MIO ", Theme.ACCENT, Theme.BOLD) + self._c("❯ ", Theme.MUTE)


__all__ = ["UI", "Theme"]
