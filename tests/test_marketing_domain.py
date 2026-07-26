"""MIO Core · Marketing & Growth Domain (Faz 3 · Domain 27) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite üzerinden. Deterministik KPI (CTR/CVR/CPA/ROAS), sıfıra-bölme dürüstlüğü,
kümülatif metrik + tutarlılık doğrulama, authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.marketing import (
    CampaignStatus,
    MarketingDomain,
    MarketingEvents,
    MarketingRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = MarketingRepository(":memory:")
    bus = EventBus(record=True)
    dom = MarketingDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def mk():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(mk):
    d, _r, _b = mk
    with pytest.raises(ValidationError):
        d.create_campaign("owner", "  ", "google")
    with pytest.raises(ValidationError):
        d.create_campaign("owner", "X", "google", budget=-1)
    with pytest.raises(UnauthorizedError):
        d.create_campaign("Reasoning", "X", "google")        # reader ama writer değil
    with pytest.raises(NotFoundError):
        d.record_metrics("owner", "yok", clicks=1)


# ---- INTEGRATION: KPI hesaplama (deterministik) ----
def test_kpis_deterministic(mk):
    d, _r, bus = mk
    c = d.create_campaign("owner", "Yaz Kampanyası", "meta", budget=1000)
    d.record_metrics("owner", c["id"], impressions=1000, clicks=100, conversions=10,
                     spend=200, revenue=800)
    perf = d.performance("owner", c["id"])
    k = perf["kpis"]
    assert k["ctr_pct"] == 10.0 and k["cvr_pct"] == 10.0         # 100/1000, 10/100
    assert k["cpc"] == 2.0 and k["cpa"] == 20.0 and k["roas"] == 4.0
    assert k["budget_used_pct"] == 20.0
    assert d.performance("owner", c["id"]) == perf               # determinizm
    assert any(e["type"] == MarketingEvents.METRICS_RECORDED for e in bus.history())


def test_zero_division_is_honest(mk):
    d, _r, _b = mk
    c = d.create_campaign("owner", "Yeni", "tiktok")             # metrik yok
    k = d.performance("owner", c["id"])["kpis"]
    assert k["ctr_pct"] is None and k["roas"] is None            # sıfıra bölme → None (uydurma yok)


def test_metrics_cumulative_and_consistency(mk):
    d, _r, _b = mk
    c = d.create_campaign("owner", "K", "google")
    d.record_metrics("owner", c["id"], impressions=500, clicks=50)
    d.record_metrics("owner", c["id"], impressions=500, clicks=50)   # kümülatif
    assert d.performance("owner", c["id"])["metrics"]["clicks"] == 100
    with pytest.raises(ValidationError):
        d.record_metrics("owner", c["id"], clicks=10000)         # clicks > impressions → tutarsız


# ---- INTEGRATION: kanal kırılımı + status ----
def test_channel_breakdown_and_status(mk):
    d, _r, _b = mk
    a = d.create_campaign("owner", "A", "google")
    b = d.create_campaign("owner", "B", "google")
    d.record_metrics("owner", a["id"], spend=100, revenue=300)
    d.record_metrics("owner", b["id"], spend=100, revenue=100)
    ch = d.channel_breakdown("owner")["channels"]
    assert ch["google"]["spend"] == 200 and ch["google"]["roas"] == 2.0    # 400/200
    d.set_status("owner", a["id"], CampaignStatus.PAUSED)
    assert d.performance("owner", a["id"])["metrics"]["spend"] == 100


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(mk):
    d, _r, _b = mk
    d.create_campaign("owner", "K", "meta")
    s = d.stats()
    assert s["campaigns"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "marketing" and "performance" in c["operations"]


# ---- SMOKE: boot() → ROAS uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    c = mio.marketing.create_campaign("owner", "Lansman", "google", budget=5000)
    mio.marketing.record_metrics("owner", c["id"], impressions=10000, clicks=500, conversions=50,
                                 spend=2000, revenue=8000)
    assert mio.marketing.performance("owner", c["id"])["kpis"]["roas"] == 4.0
    assert mio.marketing.contract()["version"] == "1.0.0"
    mio.close()
