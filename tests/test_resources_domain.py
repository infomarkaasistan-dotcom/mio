"""MIO Core · Resource & Runtime Domain (Faz 2 · Domain 19) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik probe üzerinden. Snapshot türetme,
bütçe tüketimi/aşımı, can_afford karar-öncesi kontrol, deterministik darboğaz/öneri, authorization, events ve
uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.resources import (
    ResourceEvents,
    ResourceRepository,
    ResourceRuntimeDomain,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(probe=None):
    repo = ResourceRepository(":memory:")
    bus = EventBus(record=True)
    dom = ResourceRuntimeDomain(repo, probe=probe or (lambda: {"cpu_count": 8}), bus=bus)
    return dom, repo, bus


@pytest.fixture
def rr():
    return _build()


# ---- INTEGRATION: snapshot türetme (gerçek veriden) ----
def test_snapshot_derives_ram():
    d, _r, bus = _build(lambda: {"ram_total_gb": 16.0, "ram_available_gb": 4.0, "cpu_percent": 50.0})
    snap = d.snapshot("owner")
    assert snap["ram_free_ratio"] == 0.25 and snap["ram_used_pct"] == 75.0
    assert any(e["type"] == ResourceEvents.SNAPSHOT for e in bus.history())


def test_snapshot_honest_missing_fields(rr):
    d, _r, _b = rr                                         # probe yalnız cpu_count verir
    snap = d.snapshot("owner")
    assert "ram_free_ratio" not in snap                    # veri yok → uydurma yok


# ---- UNIT: authorization ----
def test_authorization(rr):
    d, _r, _b = rr
    with pytest.raises(UnauthorizedError):
        d.snapshot("yabanci")
    with pytest.raises(UnauthorizedError):
        d.set_budget("Planning", "api", 100)               # Planning reader ama admin değil


# ---- INTEGRATION: bütçe tüketimi + aşım + can_afford ----
def test_budget_consume_and_afford(rr):
    d, _r, bus = rr
    d.set_budget("owner", "tokens", 1000, unit="token")
    assert d.can_afford("owner", "tokens", 600)["affordable"] is True
    r = d.consume("Execution", "tokens", 600)
    assert r["remaining"] == 400 and r["over_budget"] is False
    assert d.can_afford("owner", "tokens", 600)["affordable"] is False   # 600+600 > 1000
    over = d.consume("owner", "tokens", 500)               # 1100 > 1000 → aşım
    assert over["over_budget"] is True
    assert any(e["type"] == ResourceEvents.BUDGET_EXCEEDED for e in bus.history())
    with pytest.raises(NotFoundError):
        d.consume("owner", "yok-bütçe", 1)
    with pytest.raises(ValidationError):
        d.consume("owner", "tokens", -5)


def test_reset_and_status(rr):
    d, _r, _b = rr
    d.set_budget("owner", "api", 10)
    d.consume("owner", "api", 7)
    d.reset_budget("owner", "api")
    assert d.budget_status("owner")[0]["consumed"] == 0


# ---- INTEGRATION: deterministik darboğaz + öneri ----
def test_bottlenecks_and_recommendations():
    probe = lambda: {"ram_total_gb": 16.0, "ram_available_gb": 1.0, "cpu_percent": 95.0,
                     "disk_free_gb": 2.0}
    d, _r, bus = _build(probe)
    d.snapshot("owner")
    bn = d.bottlenecks("owner")
    resources = {b["resource"] for b in bn}
    assert {"ram", "cpu", "disk"} <= resources             # üçü de eşik altında/üstünde
    recs = d.recommendations("owner")
    assert any("RAM" in r for r in recs) and any("CPU" in r for r in recs)
    assert any(e["type"] == ResourceEvents.BOTTLENECK for e in bus.history())


def test_no_bottleneck_when_healthy():
    d, _r, _b = _build(lambda: {"ram_total_gb": 16.0, "ram_available_gb": 12.0, "cpu_percent": 20.0,
                                "disk_free_gb": 100.0})
    d.snapshot("owner")
    assert d.bottlenecks("owner") == []
    assert d.recommendations("owner") == ["Belirgin darboğaz/bütçe aşımı yok."]


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(rr):
    d, _r, _b = rr
    d.set_budget("owner", "cost", 5, unit="usd")
    d.consume("owner", "cost", 6)                          # aşım
    s = d.stats()
    assert s["budgets"] == 1 and s["exceeded_budgets"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "resource_runtime" and "can_afford" in c["operations"]


# ---- SMOKE: boot() → gerçek probe (donanım + disk) ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    snap = mio.resources.snapshot("owner")
    assert "platform" in snap or "cpu_count" in snap       # gerçek donanım bilgisi
    mio.resources.set_budget("owner", "llm_tokens", 100000, unit="token")
    assert mio.resources.can_afford("owner", "llm_tokens", 500)["affordable"] is True
    assert isinstance(mio.resources.recommendations("owner"), list)
    assert mio.resources.contract()["version"] == "1.0.0"
    mio.close()
