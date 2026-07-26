"""MIO Core · Media Generation Domain (Faz 4 · Domain 31) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik generator üzerinden. Durum makinesi,
connector routing, DÜRÜST no_connector (uydurma asset yok), authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.media import (
    JobStatus,
    MediaGenerationDomain,
    MediaEvents,
    MediaKind,
    MediaRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = MediaRepository(":memory:")
    bus = EventBus(record=True)
    dom = MediaGenerationDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def md():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(md):
    d, _r, _b = md
    with pytest.raises(ValidationError):
        d.generate("owner", MediaKind.IMAGE_GEN, "  ")     # prompt boş
    with pytest.raises(ValidationError):
        d.generate("owner", "uydurma", "prompt")
    with pytest.raises(UnauthorizedError):
        d.generate("Reasoning", MediaKind.IMAGE_GEN, "kedi")   # reader ama writer değil


# ---- INTEGRATION: connector YOK → DÜRÜST no_connector ----
def test_no_connector_is_honest(md):
    d, _r, bus = md
    job = d.generate("owner", MediaKind.IMAGE_GEN, "gün batımı manzarası")
    assert job["status"] == JobStatus.NO_CONNECTOR and job["result"] == {}   # uydurma asset YOK
    assert d.connectors("owner")["missing"] == sorted(MediaKind.ALL)
    assert any(e["type"] == MediaEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: connector delege ----
def test_generator_delegation(md):
    d, _r, bus = md
    def fake_img(ctx):
        return {"asset_uri": f"img://gen/{ctx['prompt'][:5]}", "params": ctx["params"]}
    d.register_generator(MediaKind.IMAGE_GEN, fake_img, name="fake-sd")
    job = d.generate("owner", MediaKind.IMAGE_GEN, "kırmızı elma", params={"size": "512"})
    assert job["status"] == JobStatus.COMPLETED and job["connector"] == "fake-sd"
    assert job["result"]["asset_uri"].startswith("img://gen/") and job["result"]["params"]["size"] == "512"
    assert d.connectors("owner")["available"] == [MediaKind.IMAGE_GEN]
    assert any(e["type"] == MediaEvents.JOB_COMPLETED for e in bus.history())


def test_generator_failure_becomes_failed(md):
    d, _r, _b = md
    d.register_generator(MediaKind.VIDEO_GEN, lambda ctx: (_ for _ in ()).throw(RuntimeError("gpu yok")))
    job = d.generate("owner", MediaKind.VIDEO_GEN, "tanıtım videosu")
    assert job["status"] == JobStatus.FAILED and "gpu yok" in job["error"]


# ---- INTEGRATION: get + list + stats + contract ----
def test_get_list_stats_contract(md):
    d, _r, _b = md
    j = d.generate("owner", MediaKind.IMAGE_GEN, "x")
    assert d.get_job("owner", j["id"])["id"] == j["id"]
    assert len(d.list_jobs("owner", kind=MediaKind.IMAGE_GEN)) == 1
    with pytest.raises(NotFoundError):
        d.get_job("owner", "yok")
    s = d.stats()
    assert s["jobs"] == 1 and s["no_connector"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "media_generation" and "generate" in c["operations"]


# ---- SMOKE: boot() → dürüst no_connector ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    job = mio.media.generate("owner", MediaKind.IMAGE_GEN, "marka logosu")
    assert job["status"] == JobStatus.NO_CONNECTOR          # dürüst: gerçek üretim modeli bağlı değil
    assert mio.media.contract()["version"] == "1.0.0"
    mio.close()
