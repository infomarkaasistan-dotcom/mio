"""MIO Core · Interface Architecture — Anayasa fitness testi (docs/constitution/INTERFACE_ARCHITECTURE.md).

Altın Kural: İş mantığı hiçbir arayüzün içinde OLMAZ. Arayüz modülleri (cli/http_api) domain/repository iç
modüllerini import ETMEZ — yalnız Application Service Layer (appservice) + sunum (cli_ui/cli_render). Böylece
CLI ve HTTP (ve gelecek Dashboard/Mobile) AYNI DTO'ları farklı render eder; iş mantığı bir kez yürür."""

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
INTERFACE_MODULES = ["mio_core/cli.py", "mio_core/http_api.py"]

# Arayüzde YASAK importlar (iş mantığı): domain iç modülleri, repository, connector adapter iç'leri.
_FORBIDDEN = re.compile(r"mio_core\.domains(\.|$)|repository|mio_core\.connectors\.adapters")


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module)
        elif isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
    return out


@pytest.mark.parametrize("mod", INTERFACE_MODULES)
def test_interface_has_no_business_logic_imports(mod):
    """Arayüz modülü domain/repository/adapter iç modüllerini import ETMEZ (iş mantığı yok)."""
    offenders = [imp for imp in _imports(REPO / mod) if _FORBIDDEN.search(imp)]
    assert not offenders, f"{mod} iş-mantığı importu içeriyor (Interface Architecture ihlali): {offenders}"


@pytest.mark.parametrize("mod", INTERFACE_MODULES)
def test_interface_uses_appservice(mod):
    """Arayüz modülü Application Service Layer'ı (appservice) kullanır."""
    assert "mio_core.appservice" in _imports(REPO / mod) or "appservice" in \
        (REPO / mod).read_text(encoding="utf-8")


def test_cli_and_http_share_same_dtos(tmp_path):
    """AYNI Application Service → AYNI DTO: CLI ve HTTP aynı veriyi alır (yalnız sunum farkı)."""
    from mio_core.runtime import boot
    from mio_core import appservice
    from mio_core.cli import dispatch
    from mio_core.http_api import route_request
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        for cmd, path in (("executive", "/executive"), ("diagnose", "/diagnose"),
                          ("hardware", "/hardware"), ("models", "/models")):
            _c, _k, cli_data = dispatch(mio, [cmd])
            _st, http_data = route_request(mio, "GET", path, {}, None)
            svc = getattr(appservice, {"executive": "executive_summary", "diagnose": "diagnose",
                                       "hardware": "hardware_report", "models": "models_overview"}[cmd])(mio)
            # üçü de aynı Application Service DTO'sunun anahtarlarını taşır (deterministik yapı)
            assert set(cli_data.keys()) == set(http_data.keys()) == set(svc.keys())
    finally:
        mio.close()


def test_constitution_doc_exists():
    assert (REPO / "docs/constitution/INTERFACE_ARCHITECTURE.md").exists()
