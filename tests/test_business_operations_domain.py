"""MIO Core · Business & Operations Domain (Faz 3 · Domain 24) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite üzerinden. Deterministik süreç analizi/darboğaz, iş kuralı motoru,
authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.business_operations import (
    BizEvents,
    BusinessOperationsDomain,
    BusinessRepository,
    ProcessStatus,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus

_STEPS = [
    {"name": "sipariş al", "role": "sales", "duration_hours": 1, "automatable": True},
    {"name": "manuel onay", "role": "manager", "duration_hours": 8, "automatable": False},
    {"name": "kargola", "role": "ops", "duration_hours": 1, "automatable": True},
]


def _build():
    repo = BusinessRepository(":memory:")
    bus = EventBus(record=True)
    dom = BusinessOperationsDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def bo():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(bo):
    d, _r, _b = bo
    with pytest.raises(ValidationError):
        d.register_process("owner", "boş", [])
    with pytest.raises(ValidationError):
        d.register_process("owner", "x", [{"role": "a"}])      # name yok
    with pytest.raises(UnauthorizedError):
        d.register_process("Reasoning", "x", _STEPS)           # reader ama writer değil
    with pytest.raises(UnauthorizedError):
        d.analyze_process("yabanci", "x")


# ---- INTEGRATION: süreç analizi + darboğaz ----
def test_process_analysis_bottleneck(bo):
    d, _r, bus = bo
    p = d.register_process("owner", "sipariş akışı", _STEPS)
    a = d.analyze_process("owner", p["id"])
    assert a["total_hours"] == 10 and a["steps"] == 3
    assert a["bottleneck"]["step"] == "manuel onay"           # 8/10 = 0.8 > 0.4
    assert set(a["automatable_steps"]) == {"sipariş al", "kargola"}
    assert a["roles"] == ["manager", "ops", "sales"]
    with pytest.raises(NotFoundError):
        d.analyze_process("owner", "yok")
    assert any(e["type"] == BizEvents.PROCESS_ANALYZED for e in bus.history())


def test_optimize_recommendations(bo):
    d, _r, _b = bo
    p = d.register_process("owner", "akış", _STEPS)
    opt = d.optimize_process("owner", p["id"])
    assert any("otomatikleştir" in r for r in opt["recommendations"])
    assert any("Darboğaz" in r for r in opt["recommendations"])


# ---- INTEGRATION: iş kuralı motoru (deterministik) ----
def test_rule_engine(bo):
    d, _r, bus = bo
    d.register_rule("owner", "yüksek-stok", when=["stok_fazla"], then="kampanya başlat", priority=80)
    d.register_rule("owner", "düşük-stok", when=["stok_az"], then="tedarik siparişi ver", priority=90)
    d.register_rule("owner", "kritik", when=["stok_az", "sezon"], then="acil tedarik", priority=95)
    res = d.evaluate("owner", ["stok_az", "sezon"])
    actions = [a["action"] for a in res["actions"]]
    assert actions == ["acil tedarik", "tedarik siparişi ver"]   # priority sıralı, sadece uyanlar
    assert res["decision_authority"] == "Executive"              # öneri, karar değil
    with pytest.raises(ValidationError):
        d.register_rule("owner", "boş", when=[], then="x")
    with pytest.raises(ValidationError):
        d.register_rule("owner", "yüksek-stok", when=["a"], then="b")   # tekrar ad
    assert any(e["type"] == BizEvents.RULES_EVALUATED for e in bus.history())


# ---- INTEGRATION: list + stats + contract ----
def test_list_stats_contract(bo):
    d, _r, _b = bo
    d.register_process("owner", "p1", _STEPS)
    d.register_rule("owner", "r1", when=["t"], then="a")
    assert len(d.list_processes("owner", status=ProcessStatus.ACTIVE)) == 1
    assert len(d.list_rules("owner")) == 1
    s = d.stats()
    assert s["processes"] == 1 and s["rules"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "business_operations" and "evaluate" in c["operations"]


# ---- SMOKE: boot() → uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    p = mio.business_operations.register_process("owner", "onboarding", _STEPS)
    a = mio.business_operations.analyze_process("owner", p["id"])
    assert a["bottleneck"] is not None
    mio.business_operations.register_rule("owner", "gecikme", when=["sla_riski"], then="önceliklendir")
    assert mio.business_operations.evaluate("owner", ["sla_riski"])["actions"][0]["action"] == "önceliklendir"
    assert mio.business_operations.contract()["version"] == "1.0.0"
    mio.close()
