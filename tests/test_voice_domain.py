"""MIO Core · Voice Domain (Faz 4 · Domain 30) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik analyzer üzerinden. Durum makinesi,
connector routing, DÜRÜST no_connector, kind-input doğrulama, authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.voice import (
    JobStatus,
    VoiceDomain,
    VoiceEvents,
    VoiceKind,
    VoiceRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = VoiceRepository(":memory:")
    bus = EventBus(record=True)
    dom = VoiceDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def vd():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(vd):
    d, _r, _b = vd
    with pytest.raises(ValidationError):
        d.register_asset("owner", "  ")
    with pytest.raises(ValidationError):
        d.synthesize("owner", "  ")                        # synthesize metin ister
    with pytest.raises(NotFoundError):
        d.transcribe("owner", "yok")                       # transcribe asset ister
    with pytest.raises(UnauthorizedError):
        d.register_asset("Reasoning", "aud://x")           # reader ama writer değil


# ---- INTEGRATION: connector YOK → DÜRÜST no_connector ----
def test_no_connector_is_honest(vd):
    d, _r, bus = vd
    a = d.register_asset("owner", "aud://konusma.wav")
    job = d.transcribe("owner", a["id"])
    assert job["status"] == JobStatus.NO_CONNECTOR and job["result"] == {}
    tts = d.synthesize("owner", "Merhaba dünya")
    assert tts["status"] == JobStatus.NO_CONNECTOR
    assert d.connectors("owner")["missing"] == sorted(VoiceKind.ALL)
    assert any(e["type"] == VoiceEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: connector delege ----
def test_transcribe_delegation(vd):
    d, _r, bus = vd
    def fake_stt(ctx):
        return {"transcript": f"metin:{ctx['asset']['uri']}"}
    d.register_analyzer(VoiceKind.TRANSCRIBE, fake_stt, name="fake-stt")
    a = d.register_asset("owner", "aud://x.wav")
    job = d.transcribe("owner", a["id"])
    assert job["status"] == JobStatus.COMPLETED and job["result"]["transcript"] == "metin:aud://x.wav"
    assert job["connector"] == "fake-stt"
    assert any(e["type"] == VoiceEvents.JOB_COMPLETED for e in bus.history())


def test_synthesize_delegation_text_input(vd):
    d, _r, _b = vd
    def fake_tts(ctx):
        return {"audio_uri": f"tts://{len(ctx['text'])}"}
    d.register_analyzer(VoiceKind.SYNTHESIZE, fake_tts, name="fake-tts")
    job = d.synthesize("owner", "selam")
    assert job["status"] == JobStatus.COMPLETED and job["result"]["audio_uri"] == "tts://5"


def test_analyzer_failure_becomes_failed(vd):
    d, _r, _b = vd
    d.register_analyzer(VoiceKind.DIARIZE, lambda ctx: (_ for _ in ()).throw(RuntimeError("çöktü")))
    a = d.register_asset("owner", "aud://x")
    job = d.diarize("owner", a["id"])
    assert job["status"] == JobStatus.FAILED and "çöktü" in job["error"]


# ---- INTEGRATION: get + list + stats + contract ----
def test_get_list_stats_contract(vd):
    d, _r, _b = vd
    a = d.register_asset("owner", "aud://x")
    j = d.transcribe("owner", a["id"])
    assert d.get_job("owner", j["id"])["id"] == j["id"]
    assert len(d.list_jobs("owner", status=JobStatus.NO_CONNECTOR)) == 1
    s = d.stats()
    assert s["assets"] == 1 and s["jobs"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "voice" and "transcribe" in c["operations"]


# ---- SMOKE: boot() → dürüst no_connector ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    tts = mio.voice.synthesize("owner", "MIO konuşuyor")
    assert tts["status"] == JobStatus.NO_CONNECTOR          # dürüst: gerçek TTS bağlı değil
    assert mio.voice.contract()["version"] == "1.0.0"
    mio.close()
