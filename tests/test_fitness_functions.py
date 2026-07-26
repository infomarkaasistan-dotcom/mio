"""MIO Core · Fitness Functions (Production Hardening #1) — MİMARİ DEĞİŞMEZLERİ otomatik test eder.

Bunlar "iddia" değil **kanıt**tır: Anayasa'nın ve mimarinin değişmezlerini her CI/test koşusunda doğrular ve
gelecekteki regresyonları yakalar. Deterministik, dış bağımlılıksız, stdlib + dosya taraması.

Kapsanan değişmezler:
- Madde 8   : çekirdek kodda stub/placeholder (NotImplementedError/TODO/FIXME) YOK.
- Bounded Context (§4): bir domain başka domainin İÇ modülünü import ETMEZ (yalnız kendi içi / public yüzey).
- Determinizm + LLM-bağımsızlık: domain service'leri canlı LLM/gateway import ETMEZ.
- Domain sözleşmesi: her domain models+repository+contract+service+__init__+README + CONTRACT_VERSION içerir.
- Kalıcılık deseni: her repository SQLite WAL + threading.Lock kullanır (deterministik yazma).
- Kompozisyon: boot() tanımlı her domaini MIORuntime'a bağlar (attribute mevcut ve None değil)."""

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOMAINS_DIR = REPO / "mio_core" / "domains"

# Her bounded-context'in ilan ettiği evrensel dosya sözleşmesi.
# NOT: repository.py evrensel DEĞİL — bazı domainler (executive/goal_management) çekirdeğin paylaşılan
# store'larını kullanır (ExecutiveState/GoalStore). Kalıcılık deseni ayrı testte, dosya varsa doğrulanır.
REQUIRED_FILES = ("models.py", "contract.py", "service.py", "__init__.py", "README.md")

# Çekirdekte olmaması gereken stub/placeholder işaretleri (kod smell)
FORBIDDEN_MARKERS = (r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b", r"raise\s+NotImplementedError")

# software_engineering domaini stub/TODO'yu VERİ olarak tanır (görevi budur) → tüm domaini muaf tut.
_MARKER_EXEMPT_DIRS = {"software_engineering"}


def _domain_dirs():
    """contract.py içeren gerçek domain dizinleri (bounded context'ler)."""
    return sorted(d for d in DOMAINS_DIR.iterdir()
                  if d.is_dir() and (d / "contract.py").exists())


def _repo_domain_dirs():
    """Kendi kalıcılık deposuna (repository.py) sahip domainler (persistence-sahibi bounded context'ler)."""
    return [d for d in _domain_dirs() if (d / "repository.py").exists()]


def _py_files(root: Path):
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


# --------------------------------------------------------------------------- #
def test_at_least_all_main_domains_present():
    """Tüm ana domainler işlendi — regresyonda domain kaybını yakalar."""
    domains = _domain_dirs()
    assert len(domains) >= 43, f"Beklenen ≥43 domain, bulunan {len(domains)}"


def test_no_stub_or_placeholder_markers():
    """Madde 8: çekirdek kodda TODO/FIXME/XXX/NotImplementedError YOK (uydurma/eksik-bırakma yok)."""
    offenders = []
    pattern = re.compile("|".join(FORBIDDEN_MARKERS))
    for py in _py_files(REPO / "mio_core"):
        if any(part in _MARKER_EXEMPT_DIRS for part in py.parts):
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.relative_to(REPO)}:{i}: {line.strip()}")
    assert not offenders, "Stub/placeholder işareti bulundu:\n" + "\n".join(offenders)


@pytest.mark.parametrize("domain", _domain_dirs(), ids=lambda d: d.name)
def test_domain_has_required_files(domain):
    """Her domain standart bounded-context dosya sözleşmesine uyar."""
    missing = [f for f in REQUIRED_FILES if not (domain / f).exists()]
    assert not missing, f"{domain.name} eksik dosyalar: {missing}"


@pytest.mark.parametrize("domain", _domain_dirs(), ids=lambda d: d.name)
def test_domain_contract_has_version(domain):
    """Her domain sözleşmesi versiyonludur (CONTRACT_VERSION)."""
    text = (domain / "contract.py").read_text(encoding="utf-8")
    assert re.search(r'CONTRACT_VERSION\s*=\s*["\']\d+\.\d+\.\d+["\']', text), \
        f"{domain.name}: CONTRACT_VERSION (semver) bulunamadı"


@pytest.mark.parametrize("domain", _repo_domain_dirs(), ids=lambda d: d.name)
def test_repository_is_deterministic_persistence(domain):
    """Kalıcılık deseni: repository.py'si OLAN her domain SQLite WAL + threading.Lock kullanır."""
    text = (domain / "repository.py").read_text(encoding="utf-8")
    assert "journal_mode=WAL" in text, f"{domain.name}: repository WAL kullanmıyor"
    assert "threading.Lock" in text, f"{domain.name}: repository threading.Lock kullanmıyor"


def test_most_domains_own_persistence():
    """Domainlerin ezici çoğunluğu kendi kalıcılık deposuna sahiptir (write-through SQLite deseni)."""
    total, with_repo = len(_domain_dirs()), len(_repo_domain_dirs())
    assert with_repo >= total - 5, f"{total} domainden yalnız {with_repo} tanesi repository sahibi (beklenen ≥ {total-5})"


@pytest.mark.parametrize("domain", _domain_dirs(), ids=lambda d: d.name)
def test_domain_service_is_llm_independent(domain):
    """Determinizm + LLM-bağımsızlık: domain service canlı LLM/gateway import ETMEZ."""
    text = (domain / "service.py").read_text(encoding="utf-8")
    forbidden = ("ModelGateway", "import ollama", "from mio_core.gateway", ".gateway import")
    hits = [f for f in forbidden if f in text]
    assert not hits, f"{domain.name}: service LLM/gateway'e bağımlı görünüyor: {hits}"


def test_bounded_context_isolation():
    """§4 Bounded Context: bir domain başka domainin İÇ modülünü import ETMEZ."""
    inner = re.compile(r"from\s+mio_core\.domains\.([a-z_]+)\.(models|repository|service|contract)\s+import")
    offenders = []
    for domain in _domain_dirs():
        for py in _py_files(domain):
            for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                m = inner.search(line)
                if m and m.group(1) != domain.name:      # kendi iç modülü serbest; başkasınınki değil
                    offenders.append(f"{py.relative_to(REPO)}:{i}: {line.strip()}")
    assert not offenders, "Cross-domain iç import (izolasyon ihlali):\n" + "\n".join(offenders)


@pytest.mark.parametrize("domain", _domain_dirs(), ids=lambda d: d.name)
def test_domain_init_exports_public_surface(domain):
    """Her domain __init__ bir __all__ public yüzeyi ilan eder (kapsülleme)."""
    tree = ast.parse((domain / "__init__.py").read_text(encoding="utf-8"))
    has_all = any(isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets) for n in tree.body)
    assert has_all, f"{domain.name}: __init__ __all__ ilan etmiyor"


def test_ci_workflow_references_real_gates():
    """CI taslağı (varsa) gerçek gate dosyalarına işaret eder — ölü CI referansını yakalar."""
    ci = REPO / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        pytest.skip("CI workflow yok (repo git değil olabilir)")
    text = ci.read_text(encoding="utf-8")
    for gate in ("tests/test_fitness_functions.py", "tests/test_operational_readiness.py"):
        assert gate in text, f"CI workflow '{gate}' gate'ine referans vermiyor"
        assert (REPO / gate).exists(), f"CI '{gate}' referans veriyor ama dosya yok"
    assert "pytest" in text, "CI workflow pytest koşmuyor"


def test_boot_wires_all_faz5_domains(tmp_path):
    """Kompozisyon: boot() Faz 5 dahil tüm ana domainleri MIORuntime'a bağlar (attribute mevcut, None değil)."""
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        expected = [
            # Faz 5 (Distributed & Ecosystem)
            "model_management", "multi_agent", "marketplace_domain", "knowledge_marketplace",
            "federation", "distributed_execution", "autonomous_operations", "digital_twin", "extension_sdk",
            # Faz 4 (Multimodal & Integration) temsilcileri
            "vision", "voice", "media", "web", "device", "iot",
        ]
        for name in expected:
            assert hasattr(mio, name), f"boot() '{name}' domainini bağlamadı"
            assert getattr(mio, name) is not None, f"'{name}' None"
            # her domain versiyonlu bir contract() sunar
            assert getattr(mio, name).contract()["version"], f"'{name}' contract versiyonsuz"
    finally:
        mio.close()
