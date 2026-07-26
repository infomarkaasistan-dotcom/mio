"""MIO Core · Vision Domain (Faz 4 · Domain 29) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik analyzer üzerinden. Durum makinesi,
connector routing, DÜRÜST no_connector (uydurma yok), authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.vision import (
    AnalysisKind,
    JobStatus,
    VisionDomain,
    VisionEvents,
    VisionRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = VisionRepository(":memory:")
    bus = EventBus(record=True)
    dom = VisionDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def vd():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(vd):
    d, _r, _b = vd
    with pytest.raises(ValidationError):
        d.register_asset("owner", "  ")
    a = d.register_asset("owner", "img://x.png")
    with pytest.raises(ValidationError):
        d.analyze("owner", a["id"], "uydurma-analiz")
    with pytest.raises(NotFoundError):
        d.analyze("owner", "yok", AnalysisKind.OCR)
    with pytest.raises(UnauthorizedError):
        d.register_asset("Reasoning", "img://y")           # reader ama writer değil


# ---- INTEGRATION: connector YOK → DÜRÜST no_connector (uydurma yok) ----
def test_no_connector_is_honest(vd):
    d, _r, bus = vd
    a = d.register_asset("owner", "img://belge.png")
    job = d.analyze("owner", a["id"], AnalysisKind.OCR)
    assert job["status"] == JobStatus.NO_CONNECTOR and job["result"] == {}   # uydurma sonuç YOK
    assert d.connectors("owner")["missing"] == sorted(AnalysisKind.ALL)
    assert any(e["type"] == VisionEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: connector bağlıysa delege + completed ----
def test_analyzer_delegation_completed(vd):
    d, _r, bus = vd
    def fake_ocr(asset):
        return {"text": f"OCR:{asset['uri']}"}
    d.register_analyzer(AnalysisKind.OCR, fake_ocr, name="fake-ocr")
    a = d.register_asset("owner", "img://fatura.png")
    job = d.analyze("owner", a["id"], AnalysisKind.OCR)
    assert job["status"] == JobStatus.COMPLETED and job["connector"] == "fake-ocr"
    assert job["result"]["text"] == "OCR:img://fatura.png"
    assert d.connectors("owner")["available"] == [AnalysisKind.OCR]
    assert any(e["type"] == VisionEvents.JOB_COMPLETED for e in bus.history())


def test_analyzer_failure_becomes_job_failed(vd):
    d, _r, bus = vd
    def broken(asset):
        raise RuntimeError("model çöktü")
    d.register_analyzer(AnalysisKind.CAPTION, broken)
    a = d.register_asset("owner", "img://x")
    job = d.analyze("owner", a["id"], AnalysisKind.CAPTION)
    assert job["status"] == JobStatus.FAILED and "model çöktü" in job["error"]   # dürüst hata, sistem bozulmaz
    assert any(e["type"] == VisionEvents.JOB_FAILED for e in bus.history())


# ---- INTEGRATION: list + get + stats + contract ----
def test_list_get_stats_contract(vd):
    d, _r, _b = vd
    a = d.register_asset("owner", "img://x", width=800, height=600)
    j = d.analyze("owner", a["id"], AnalysisKind.OCR)
    assert d.get_job("owner", j["id"])["id"] == j["id"]
    assert len(d.list_jobs("owner", status=JobStatus.NO_CONNECTOR)) == 1
    assert len(d.list_assets("owner")) == 1
    with pytest.raises(NotFoundError):
        d.get_job("owner", "yok")
    s = d.stats()
    assert s["assets"] == 1 and s["jobs"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "vision" and "analyze" in c["operations"]


# ---- SMOKE: boot() → dürüst no_connector (gerçek vision bağlı değil) ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    a = mio.vision.register_asset("owner", "img://screenshot.png")
    job = mio.vision.analyze("owner", a["id"], AnalysisKind.OCR)
    assert job["status"] == JobStatus.NO_CONNECTOR          # dürüst: gerçek OCR bağlı değil
    assert mio.vision.connectors("owner")["available"] == []
    assert mio.vision.contract()["version"] == "1.0.0"
    mio.close()
