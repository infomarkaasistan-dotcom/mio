"""MIO Core · Research Domain (Faz 3 · Domain 21) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite üzerinden. Deterministik sentez (corroboration/doğrulama), tek-kaynak
işaretleme, authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.research import (
    Credibility,
    InquiryStatus,
    ResearchDomain,
    ResearchEvents,
    ResearchRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = ResearchRepository(":memory:")
    bus = EventBus(record=True)
    dom = ResearchDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def rd():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(rd):
    d, _r, _b = rd
    with pytest.raises(ValidationError):
        d.start_inquiry("owner", "  ")
    q = d.start_inquiry("Research", "Pazar büyüklüğü ne?")
    with pytest.raises(ValidationError):
        d.add_finding("owner", q["id"], "x", credibility="çok")
    with pytest.raises(NotFoundError):
        d.add_finding("owner", "yok", "x")
    with pytest.raises(UnauthorizedError):
        d.start_inquiry("yabanci", "soru")
    with pytest.raises(UnauthorizedError):
        d.add_finding("Reasoning", q["id"], "x")           # reader ama writer değil


# ---- INTEGRATION: deterministik sentez (corroboration) ----
def test_synthesis_corroboration_and_single_source(rd):
    d, _r, bus = rd
    q = d.start_inquiry("owner", "Talep artıyor mu?")
    d.add_finding("owner", q["id"], "Talep artıyor", source="raporA", credibility=Credibility.HIGH)
    d.add_finding("owner", q["id"], "talep artıyor", source="raporB", credibility=Credibility.MEDIUM)
    d.add_finding("owner", q["id"], "Fiyatlar düşüyor", source="raporA", credibility=Credibility.LOW)
    rep = d.synthesize("owner", q["id"])
    corrob = {c["statement"].lower(): c for c in rep["corroborated"]}
    assert "talep artıyor" in corrob and corrob["talep artıyor"]["distinct_sources"] == 2   # 2 kaynak
    assert any(s["statement"] == "Fiyatlar düşüyor" for s in rep["single_source_unverified"])
    assert rep["distinct_sources"] == 2
    # sentez soruşturmayı işaretledi
    assert d.list_inquiries("owner", status=InquiryStatus.SYNTHESIZED)[0]["id"] == q["id"]
    assert any(e["type"] == ResearchEvents.SYNTHESIZED for e in bus.history())


def test_verified_boosts_corroboration(rd):
    d, _r, _b = rd
    q = d.start_inquiry("owner", "Tek kaynak ama doğrulanmış?")
    f = d.add_finding("owner", q["id"], "X doğru", source="tek", credibility=Credibility.MEDIUM)
    # tek kaynak → başta corroborated değil
    assert not d.report("owner", q["id"])["corroborated"]
    d.verify_finding("owner", f["id"])
    rep = d.report("owner", q["id"])
    assert rep["corroborated"] and rep["corroborated"][0]["verified"] is True   # doğrulama → corroborated
    with pytest.raises(NotFoundError):
        d.verify_finding("owner", "yok-bulgu")


# ---- INTEGRATION: report deterministik + read-only ----
def test_report_is_deterministic_and_readonly(rd):
    d, _r, _b = rd
    q = d.start_inquiry("owner", "S")
    d.add_finding("owner", q["id"], "A", source="s1")
    r1 = d.report("owner", q["id"])
    r2 = d.report("owner", q["id"])
    assert r1 == r2                                        # determinizm
    assert d.list_inquiries("owner", status=InquiryStatus.OPEN)   # report durum değiştirmedi


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(rd):
    d, _r, _b = rd
    q = d.start_inquiry("owner", "S")
    d.add_finding("owner", q["id"], "A", source="s1")
    s = d.stats()
    assert s["inquiries"] == 1 and s["findings"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "research" and "synthesize" in c["operations"]


# ---- SMOKE: boot() → uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    q = mio.research.start_inquiry("owner", "Rakip fiyatı düşürdü mü?")
    mio.research.add_finding("owner", q["id"], "Rakip fiyat düşürdü", source="izlemeA", credibility=Credibility.HIGH)
    mio.research.add_finding("owner", q["id"], "rakip fiyat düşürdü", source="izlemeB", credibility=Credibility.HIGH)
    rep = mio.research.synthesize("owner", q["id"])
    assert rep["corroborated"] and rep["corroborated"][0]["distinct_sources"] == 2
    assert mio.research.contract()["version"] == "1.0.0"
    mio.close()
