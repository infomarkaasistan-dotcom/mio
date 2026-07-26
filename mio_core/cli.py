"""MIO Core · CLI (Interface Katmanı #1) — terminalden etkileşimli kabuk + tek-atış komutlar, stdlib-only.

Canlı runtime'a bağlanır; sistemi keşfetmeyi/kullanmayı/hata-ayıklamayı sağlar. DETERMİNİSTİK ve LLM-BAĞIMSIZ
(Anayasa: LLM danışman, karar verici değil). Doğal dil, ancak bir LLM danışman bağlıysa (connector) anlamlıdır;
burada birincil arayüz **deterministik komutlar**dır — her zaman çalışır.

Komutlar:
  domains                         → tüm domainleri + sözleşme versiyonu + kısa açıklama listeler
  contract <domain>               → domainin public sözleşmesini gösterir (operasyonlar/events/invariantlar)
  stats <domain>                  → domainin metriklerini gösterir
  metrics                         → tüm domainlerin birleşik metrik snapshot'ı (JSON)
  prometheus                      → Prometheus text exposition (Monitoring Adapter)
  readiness | health              → operasyonel hazırlık / sağlık (readiness ready değilse çıkış kodu 1)
  events [N]                      → son N event bus olayı (varsayılan 20)
  call <domain> <op> [json]       → bir domain operasyonunu reflektif çağırır (json = {"actor":"owner",...})
  connectors                      → kayıtlı connector'lar (kategori/capability/öncelik/health)
  capabilities                    → capability → sağlayan connector'lar kataloğu
  execute <capability> [json]     → capability'yi Connector Manager'a çalıştırt (connector yoksa unavailable)
  serve [--host H --port P]       → HTTP API adapter'ını başlatır (stdlib http.server; aynı appservice)
  help                            → bu yardım
  quit | exit                     → çık (etkileşimli mod)"""

from __future__ import annotations

import json
import shlex
import sys
from typing import Any, Optional

from mio_core import appservice
from mio_core.appservice import BadRequest, NotFound

_BANNER = ("MIO Executive OS — etkileşimli kabuk (LLM-bağımsız, deterministik).\n"
           "'help' ile komutlar, 'domains' ile domain listesi, 'quit' ile çıkış.\n")

_HELP = __doc__.split("Komutlar:", 1)[1].strip()


def _fmt(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str, sort_keys=True)


def run_command(mio, argv: list) -> tuple[int, str]:
    """Tek komutu canlı runtime üzerinde çalıştırır. (exit_code, çıktı) döner. boot/close ÇAĞIRMAZ.

    İş mantığı YOK — appservice (paylaşılan sözleşme yüzeyi) üzerinden delege eder; yalnız argv-parse + biçimleme."""
    if not argv:
        return 0, ""
    name, rest = argv[0], argv[1:]
    try:
        if name in ("help", "?", "h"):
            return 0, _HELP
        if name == "domains":
            return 0, _fmt(appservice.list_domains(mio))
        if name == "metrics":
            return 0, _fmt(appservice.metrics(mio))
        if name == "prometheus":
            return 0, appservice.prometheus_metrics(mio)     # zaten metin — biçimlemeye gerek yok
        if name == "readiness":
            r = appservice.readiness(mio)
            return (0 if r.get("ready") else 1), _fmt(r)
        if name == "health":
            return 0, _fmt(appservice.health(mio))
        if name == "events":
            limit = int(rest[0]) if rest and rest[0].isdigit() else 20
            return 0, _fmt(appservice.events(mio, limit))
        if name == "contract":
            if not rest:
                return 2, "kullanım: contract <domain>"
            return 0, _fmt(appservice.domain_contract(mio, rest[0]))
        if name == "stats":
            if not rest:
                return 2, "kullanım: stats <domain>"
            return 0, _fmt(appservice.domain_stats(mio, rest[0]))
        if name == "call":
            return _do_call(mio, rest)
        if name == "connectors":
            return 0, _fmt(appservice.connectors_overview(mio))
        if name == "capabilities":
            return 0, _fmt(appservice.capabilities_catalog(mio))
        if name == "execute":
            return _do_execute(mio, rest)
        return 2, f"bilinmeyen komut: {name}\n\n{_HELP}"
    except (NotFound, BadRequest) as exc:      # istek/kullanım hatası → 2 (client error)
        return 2, f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 — domain istisnası (authz/validation) → 1; süreci çökertmez
        return 1, f"HATA: {type(exc).__name__}: {exc}"


def _do_call(mio, rest: list) -> tuple[int, str]:
    if len(rest) < 2:
        return 2, 'kullanım: call <domain> <operasyon> [json]   ör: call iot register_thing {"actor":"owner","name":"S"}'
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
    result = appservice.call(mio, rest[0], rest[1], kwargs)   # iş mantığı domainde; burada delege
    return 0, _fmt(result)


def _do_execute(mio, rest: list) -> tuple[int, str]:
    if not rest:
        return 2, 'kullanım: execute <capability> [json]   ör: execute send_email {"to":"a@b.com"}'
    raw = " ".join(rest[1:]).strip()
    request: dict[str, Any] = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return 2, f"geçersiz JSON: {exc}"
        if not isinstance(parsed, dict):
            return 2, 'JSON bir nesne olmalı, ör: {"to":"a@b.com"}'
        request = parsed
    # capability çalıştırma ASLA çökmez; connector yoksa dürüst connector_unavailable döner
    return 0, _fmt(appservice.execute_capability(mio, rest[0], request))


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
    is_interactive = (not argv) or argv[0] == "shell"

    from mio_core.runtime import boot
    mio = boot(workspace=workspace, connect_ollama=False, discover_hw=False)
    try:
        if is_interactive:
            return interactive(mio)
        if argv[0] in ("serve", "http"):          # HTTP adapter (stdlib http.server) — bloklar
            from mio_core.http_api import serve
            serve(mio, host=host, port=int(port))
            return 0
        code, out = run_command(mio, argv)
        if out:
            print(out)
        return code
    finally:
        mio.close()


if __name__ == "__main__":
    sys.exit(main())
