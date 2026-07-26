"""MIO Core · Data Analytics Domain (Faz 3 · Domain 23) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek stdlib statistics + SQLite üzerinden. Deterministik aggregate/describe/trend/
anomali, authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.data_analytics import (
    AggOp,
    DataAnalyticsDomain,
    DataEvents,
    DataRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    analyzer,
)
from mio_core.events import EventBus

_ROWS = [
    {"ay": "Oca", "gelir": 100, "gider": 60},
    {"ay": "Şub", "gelir": 150, "gider": 70},
    {"ay": "Mar", "gelir": 120, "gider": 65},
    {"ay": "Nis", "gelir": 500, "gider": 80},   # gelir'de anomali
]


def _build():
    repo = DataRepository(":memory:")
    bus = EventBus(record=True)
    dom = DataAnalyticsDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def da():
    return _build()


# ---- UNIT: deterministik analizör ----
def test_analyzer_aggregate_and_describe():
    assert analyzer.aggregate(_ROWS, "gelir", AggOp.SUM)["value"] == 870
    assert analyzer.aggregate(_ROWS, "gelir", AggOp.MEAN)["value"] == 217.5
    assert analyzer.aggregate(_ROWS, "ay", AggOp.DISTINCT)["value"] == 4
    desc = analyzer.describe(_ROWS)
    assert desc["columns"]["gelir"]["type"] == "numeric" and desc["columns"]["ay"]["type"] == "text"


def test_analyzer_trend_and_anomaly():
    assert analyzer.trend([10, 20, 30])["direction"] == "up"
    assert analyzer.trend([30, 10])["direction"] == "down"
    an = analyzer.anomalies([100, 150, 120, 500], k=1.5)
    assert any(a["value"] == 500 for a in an["anomalies"])     # 500 sapkın


# ---- INTEGRATION: dataset + aggregate + validation + authz ----
def test_register_aggregate_authz(da):
    d, _r, bus = da
    ds = d.register_dataset("owner", "aylık", _ROWS)
    assert ds["row_count"] == 4 and "gelir" in ds["columns"]
    assert d.aggregate("owner", ds["id"], "gelir", AggOp.MAX)["value"] == 500
    with pytest.raises(ValidationError):
        d.aggregate("owner", ds["id"], "yok-sütun", AggOp.SUM)
    with pytest.raises(ValidationError):
        d.aggregate("owner", ds["id"], "gelir", "uydurma-op")
    with pytest.raises(NotFoundError):
        d.describe("owner", "yok-ds")
    with pytest.raises(UnauthorizedError):
        d.register_dataset("Reasoning", "x", [])               # reader ama writer değil
    with pytest.raises(ValidationError):
        d.register_dataset("owner", "x", "liste-değil")
    assert any(e["type"] == DataEvents.DATASET_REGISTERED for e in bus.history())


# ---- INTEGRATION: KPI + trend + anomali ----
def test_kpi_trend_anomaly(da):
    d, _r, bus = da
    ds = d.register_dataset("owner", "aylık", _ROWS)
    kpi = d.kpi("Finance", ds["id"], "toplam_gelir", "gelir", AggOp.SUM)
    assert kpi["kpi"] == "toplam_gelir" and kpi["value"] == 870
    assert d.trend("owner", [100, 150, 120, 500])["direction"] == "up"
    an = d.anomalies("owner", [100, 150, 120, 500], k=1.5)
    assert an["anomalies"] and any(e["type"] == DataEvents.ANOMALY_FOUND for e in bus.history())
    with pytest.raises(ValidationError):
        d.trend("owner", "liste-değil")


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(da):
    d, _r, _b = da
    ds = d.register_dataset("owner", "x", _ROWS)
    d.aggregate("owner", ds["id"], "gelir", AggOp.MEAN)
    s = d.stats()
    assert s["datasets"] == 1 and s["aggregations"] >= 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "data_analytics" and "aggregate" in c["operations"]


# ---- SMOKE: boot() → uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    ds = mio.data_analytics.register_dataset("owner", "satışlar",
                                             [{"gün": 1, "satış": 10}, {"gün": 2, "satış": 14}])
    assert mio.data_analytics.aggregate("owner", ds["id"], "satış", AggOp.SUM)["value"] == 24
    assert mio.data_analytics.trend("owner", [10, 14])["direction"] == "up"
    assert mio.data_analytics.contract()["version"] == "1.0.0"
    mio.close()
