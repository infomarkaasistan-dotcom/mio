"""MIO Core · `python -m mio_core` — CLI + ops/monitoring probe girişi.

Yönlendirme:
- `readiness | health | metrics`  → ops probe (exit-kodlu; Docker HEALTHCHECK / monitoring scrape backward-compat)
- diğer her şey (argsız dahil)     → etkileşimli/tek-atış CLI (mio_core.cli)
"""

import sys

_PROBE = {"readiness", "health", "metrics"}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] in _PROBE:
        from mio_core.ops import main as ops_main
        return ops_main(argv)
    from mio_core.cli import main as cli_main
    return cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
