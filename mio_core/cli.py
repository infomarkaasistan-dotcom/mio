"""MIO Core · CLI (Interface Katmanı #1) — terminalden etkileşimli kabuk + tek-atış komutlar, stdlib-only.

Canlı runtime'a bağlanır; sistemi keşfetmeyi/kullanmayı/hata-ayıklamayı sağlar. DETERMİNİSTİK ve LLM-BAĞIMSIZ
(Anayasa: LLM danışman, karar verici değil). Doğal dil, ancak bir LLM danışman bağlıysa (connector) anlamlıdır;
burada birincil arayüz **deterministik komutlar**dır — her zaman çalışır.

Komutlar:
  domains                         → tüm domainleri + sözleşme versiyonu + kısa açıklama listeler
  contract <domain>               → domainin public sözleşmesini gösterir (operasyonlar/events/invariantlar)
  stats <domain>                  → domainin metriklerini gösterir
  metrics                         → tüm domainlerin birleşik metrik snapshot'ı
  readiness | health              → operasyonel hazırlık / sağlık (readiness ready değilse çıkış kodu 1)
  events [N]                      → son N event bus olayı (varsayılan 20)
  call <domain> <op> [json]       → bir domain operasyonunu reflektif çağırır (json = {"actor":"owner",...})
  help                            → bu yardım
  quit | exit                     → çık (etkileşimli mod)"""

from __future__ import annotations

import json
import shlex
import sys
from typing import Any, Optional

from mio_core.runtime import _READINESS_DOMAINS

_BANNER = ("MIO Executive OS — etkileşimli kabuk (LLM-bağımsız, deterministik).\n"
           "'help' ile komutlar, 'domains' ile domain listesi, 'quit' ile çıkış.\n")

_HELP = __doc__.split("Komutlar:", 1)[1].strip()


def _fmt(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str, sort_keys=True)


def _domains_overview(mio) -> list[dict[str, Any]]:
    out = []
    for name in _READINESS_DOMAINS:
        obj = getattr(mio, name, None)
        if obj is None or not hasattr(obj, "contract"):
            continue
        try:
            c = obj.contract()
            out.append({"domain": name, "version": c.get("version"),
                        "operations": len(c.get("operations", [])),
                        "description": (c.get("description", "") or "")[:80]})
        except Exception as exc:  # noqa: BLE001
            out.append({"domain": name, "error": str(exc)[:80]})
    return out


def run_command(mio, argv: list) -> tuple[int, str]:
    """Tek komutu canlı runtime üzerinde çalıştırır. (exit_code, çıktı) döner. boot/close ÇAĞIRMAZ."""
    if not argv:
        return 0, ""
    name, rest = argv[0], argv[1:]
    try:
        if name in ("help", "?", "h"):
            return 0, _HELP
        if name == "domains":
            return 0, _fmt(_domains_overview(mio))
        if name == "metrics":
            return 0, _fmt(mio.metrics())
        if name == "readiness":
            r = mio.readiness()
            return (0 if r.get("ready") else 1), _fmt(r)
        if name == "health":
            return 0, _fmt(mio.health())
        if name == "events":
            limit = int(rest[0]) if rest and rest[0].isdigit() else 20
            evts = [{"type": e.get("type"), "data": e.get("data")} for e in mio.bus.history(limit=limit)]
            return 0, _fmt(evts)
        if name in ("contract", "stats"):
            if not rest:
                return 2, f"kullanım: {name} <domain>"
            obj = getattr(mio, rest[0], None)
            if obj is None:
                return 2, f"domain bulunamadı: {rest[0]}"
            meth = getattr(obj, name, None)
            if not callable(meth):
                return 2, f"{rest[0]}.{name}() yok"
            return 0, _fmt(meth())
        if name == "call":
            return _do_call(mio, rest)
        return 2, f"bilinmeyen komut: {name}\n\n{_HELP}"
    except Exception as exc:  # noqa: BLE001 — CLI hatası çıktıya döner, süreci çökertmez
        return 1, f"HATA: {type(exc).__name__}: {exc}"


def _do_call(mio, rest: list) -> tuple[int, str]:
    if len(rest) < 2:
        return 2, 'kullanım: call <domain> <operasyon> [json]   ör: call iot register_thing {"actor":"owner","name":"S"}'
    dname, opname = rest[0], rest[1]
    obj = getattr(mio, dname, None)
    if obj is None:
        return 2, f"domain bulunamadı: {dname}"
    if opname.startswith("_"):
        return 2, "özel (underscore) metod çağrılamaz"
    fn = getattr(obj, opname, None)
    if not callable(fn):
        return 2, f"operasyon bulunamadı: {dname}.{opname}"
    raw = " ".join(rest[2:]).strip()
    kwargs: dict[str, Any] = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return 2, f"geçersiz JSON: {exc}"
        if not isinstance(parsed, dict):
            return 2, 'JSON bir nesne olmalı, ör: {"actor":"owner","name":"S"}'
        kwargs = parsed
    result = fn(**kwargs)
    return 0, _fmt(result)


def interactive(mio) -> int:
    """Etkileşimli REPL (gerçek terminal). Testler run_command'ı doğrudan kullanır."""
    sys.stdout.write(_BANNER)
    while True:
        try:
            line = input("mio> ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.stdout.write("\n")
            return 0
        if not line:
            continue
        if line in ("quit", "exit", "q"):
            return 0
        _code, out = run_command(mio, shlex.split(line))
        if out:
            print(out)


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    workspace = ".mio"
    if "--workspace" in argv:
        i = argv.index("--workspace")
        if i + 1 < len(argv):
            workspace = argv[i + 1]
            del argv[i:i + 2]
    is_interactive = (not argv) or argv[0] == "shell"

    from mio_core.runtime import boot
    mio = boot(workspace=workspace, connect_ollama=False, discover_hw=False)
    try:
        if is_interactive:
            return interactive(mio)
        code, out = run_command(mio, argv)
        if out:
            print(out)
        return code
    finally:
        mio.close()


if __name__ == "__main__":
    sys.exit(main())
