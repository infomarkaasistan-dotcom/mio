"""MIO Core · Software Engineering Domain (Faz 3 · Domain 20) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek stdlib `ast` analizi + SQLite registry üzerinden. Deterministik analiz,
Anayasa quality gate (placeholder/stub/TODO reddi), artifact/task yönetimi, authorization, events ve
uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.software_engineering import (
    SEEvents,
    SoftwareEngineeringDomain,
    SoftwareRepository,
    TaskKind,
    TaskStatus,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    analyze,
)
from mio_core.events import EventBus

_CLEAN = '''
def add(a, b):
    """İki sayıyı toplar."""
    return a + b
'''

_STUB = '''
def not_done():
    pass

def todo_here():
    return 1  # TODO: düzelt
'''


def _build():
    repo = SoftwareRepository(":memory:")
    bus = EventBus(record=True)
    dom = SoftwareEngineeringDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def se():
    return _build()


# ---- UNIT: deterministik analiz (ast) ----
def test_analyze_is_deterministic_and_real():
    r1 = analyze(_CLEAN)
    r2 = analyze(_CLEAN)
    assert r1 == r2                                        # determinizm
    assert r1["metrics"]["functions"] == 1 and r1["valid"] is True
    assert r1["metrics"]["docstring_coverage"] == 1.0 and r1["issue_count"] == 0


def test_analyze_detects_stub_and_placeholder():
    r = analyze(_STUB)
    kinds = {i["kind"] for i in r["issues"]}
    assert "stub" in kinds and "placeholder" in kinds     # pass-only + TODO
    assert r["metrics"]["functions"] == 2


def test_analyze_syntax_error():
    r = analyze("def broken(:\n  pass")
    assert r["valid"] is False and any(i["kind"] == "syntax_error" for i in r["issues"])


# ---- INTEGRATION: Anayasa quality gate ----
def test_quality_gate_rejects_placeholder(se):
    d, _r, bus = se
    ok = d.quality_gate("Engineering", _CLEAN)
    assert ok["passed"] is True and ok["verdict"] == "pass"
    bad = d.quality_gate("Engineering", _STUB)
    assert bad["passed"] is False and bad["verdict"] == "reject" and bad["blocking_issues"]
    assert any(e["type"] == SEEvents.QUALITY_GATE for e in bus.history())


# ---- UNIT: authorization ----
def test_authorization(se):
    d, _r, _b = se
    with pytest.raises(UnauthorizedError):
        d.analyze_code("yabanci", _CLEAN)
    with pytest.raises(UnauthorizedError):
        d.register_artifact("Reasoning", "x.py")           # reader ama writer değil


# ---- INTEGRATION: artifact + task yaşam-döngüsü ----
def test_artifact_and_task_lifecycle(se):
    d, _r, bus = se
    with pytest.raises(ValidationError):
        d.register_artifact("owner", "  ")
    art = d.register_artifact("owner", "mio_core/x.py", kind="module")
    t = d.create_task("owner", "X ekle", kind=TaskKind.FEATURE, artifact_id=art["id"])
    assert t["status"] == TaskStatus.OPEN
    d.update_task_status("owner", t["id"], TaskStatus.DONE)
    assert d.list_tasks("owner", status=TaskStatus.DONE)[0]["id"] == t["id"]
    with pytest.raises(NotFoundError):
        d.create_task("owner", "Y", artifact_id="yok-art")
    with pytest.raises(ValidationError):
        d.create_task("owner", "Z", kind="uydurma")
    with pytest.raises(NotFoundError):
        d.update_task_status("owner", "yok", TaskStatus.DONE)
    assert any(e["type"] == SEEvents.TASK_CREATED for e in bus.history())


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(se):
    d, _r, _b = se
    d.analyze_code("owner", _CLEAN)
    d.register_artifact("owner", "a.py")
    d.create_task("owner", "iş")
    s = d.stats()
    assert s["analyses"] >= 1 and s["artifacts"] == 1 and s["tasks"] == 1
    assert s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "software_engineering" and "quality_gate" in c["operations"]


# ---- SMOKE: boot() → gerçek quality gate MIO'nun kendi kodunda ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    gate = mio.software_engineering.quality_gate("owner", _CLEAN)
    assert gate["passed"] is True
    assert mio.software_engineering.quality_gate("owner", _STUB)["passed"] is False
    assert mio.software_engineering.contract()["version"] == "1.0.0"
    mio.close()
