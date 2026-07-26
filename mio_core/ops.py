"""MIO Core · Ops entrypoint (Production Hardening #7) — deployment/monitoring probe, stdlib-only.

`python -m mio_core <command>` → runtime'ı boot eder, deterministik bir gözlem çıktısı (JSON) verir ve uygun
çıkış koduyla döner. Container HEALTHCHECK / readiness probe / monitoring scrape için tasarlanmıştır.

Komutlar:
  readiness  → mio.readiness() ; hazırsa exit 0, değilse exit 1  (K8s readiness probe muadili)
  health     → mio.health()    ; exit 0
  metrics    → mio.metrics()   ; exit 0  (tüm domain stats + bus sağlığı — monitoring scrape)

NOT: MIO çekirdeği gömülebilir bir RUNTIME'dır (dahili HTTP sunucusu YOK). Bu probe, host/orkestratörün
sağlık/monitoring kancası olarak kullanılır. Gerçek servis/API katmanı ayrı bir gelecek çıktısıdır."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, Optional

_COMMANDS = ("readiness", "health", "metrics")


def run_probe(command: str, *, workspace: str = ".mio", connect_ollama: bool = False,
              discover_hw: bool = False, boot_fn: Optional[Callable] = None) -> tuple[int, dict[str, Any]]:
    """Runtime'ı boot eder, komutu koşar, (exit_code, payload) döner. boot_fn enjekte edilebilir (test)."""
    if command not in _COMMANDS:
        return 2, {"error": f"bilinmeyen komut: {command}", "valid": list(_COMMANDS)}
    if boot_fn is None:
        from mio_core.runtime import boot as boot_fn  # lazy import (hızlı --help)
    mio = boot_fn(workspace=workspace, connect_ollama=connect_ollama, discover_hw=discover_hw)
    try:
        if command == "readiness":
            r = mio.readiness()
            return (0 if r.get("ready") else 1), r
        if command == "health":
            return 0, mio.health()
        return 0, mio.metrics()          # metrics
    finally:
        mio.close()


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="mio_core",
                                     description="MIO Executive OS — ops/monitoring probe")
    parser.add_argument("command", nargs="?", default="readiness", choices=_COMMANDS,
                        help="readiness | health | metrics")
    parser.add_argument("--workspace", default=".mio", help="runtime workspace dizini")
    parser.add_argument("--connect-ollama", action="store_true", help="Ollama'ya bağlan (varsayılan kapalı)")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    code, payload = run_probe(args.command, workspace=args.workspace,
                              connect_ollama=args.connect_ollama)
    print(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
