"""MIO Core · Media Connector Pack — TTS/STT/FFmpeg gerçek adapter'ları (enjekte transport → deterministik).

FFmpeg yerel gerçek (runner enjekte); TTS/STT gerçek kod + enjekte urlopen. Presentation niyetlerinin Executive
köprüsü üzerinden gerçek media connector ile YÜRÜTÜLDÜĞÜ (executed) uçtan-uca doğrulanır."""

import json

import pytest

from mio_core.connectors import Cap, ConnectorCategory
from mio_core.connectors.adapters import (
    ffmpeg_connector,
    openai_tts_connector,
    piper_tts_connector,
    whisper_connector,
)
from mio_core.connectors.models import ValidationError


class _Proc:
    def __init__(self, rc=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = rc, stdout, stderr


class _Resp:
    def __init__(self, payload, status=200):
        self._p = json.dumps(payload).encode("utf-8")
        self.status = status
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return self._p


# ---- TTS (OpenAI-uyumlu) ----
def test_openai_tts_synthesize_injected():
    seen = {}
    def fake(req, timeout=30):
        seen["auth"] = req.headers.get("Authorization"); return _Resp({}, 200)
    c = openai_tts_connector(api_key="sk-x", urlopen=fake)
    assert c.category == ConnectorCategory.MEDIA and c.provides(Cap.SPEECH_SYNTHESIZE)
    out = c.execute(Cap.SPEECH_SYNTHESIZE, {"text": "merhaba dunya", "voice": "nova"})
    assert out["synthesized"] and out["chars"] == 13 and out["voice"] == "nova"
    assert seen["auth"] == "Bearer sk-x"                # anahtar header'da (loglanmaz)
    assert openai_tts_connector(api_key="").health().ok is False


# ---- TTS (Piper yerel) ----
def test_piper_tts_injected_runner():
    calls = {}
    def runner(args, input=None, capture_output=True, text=True, timeout=60):
        calls["args"] = args; calls["input"] = input; return _Proc(rc=0)
    c = piper_tts_connector(model_path="/m/tr.onnx", runner=runner)
    out = c.execute(Cap.SPEECH_SYNTHESIZE, {"text": "selam", "out": "a.wav"})
    assert out["synthesized"] and "--output_file" in calls["args"] and calls["input"] == "selam"


# ---- STT (Whisper) ----
def test_whisper_transcribe_injected():
    c = whisper_connector(api_key="k", urlopen=lambda req, timeout=30: _Resp({"text": "çözümlenen metin"}))
    out = c.execute(Cap.SPEECH_TRANSCRIBE, {"audio_ref": "rec://1"})
    assert out["text"] == "çözümlenen metin"


# ---- FFmpeg (yerel, enjekte runner) ----
def test_ffmpeg_convert_injected():
    calls = {}
    def runner(args, capture_output=True, text=True, timeout=300):
        calls["args"] = args; return _Proc(rc=0)
    c = ffmpeg_connector(runner=runner)
    assert c.provides(Cap.AUDIO_CONVERT) and c.provides(Cap.VIDEO_ENCODE)
    out = c.execute(Cap.AUDIO_CONVERT, {"input": "a.wav", "output": "a.mp3"})
    assert out["ok"] and "a.mp3" in calls["args"] and "-i" in calls["args"]
    with pytest.raises(ValidationError):
        c.execute(Cap.AUDIO_CONVERT, {"input": "a.wav"})   # output eksik


# ---- register_from_env media connector'ları bağlar ----
def test_bootstrap_registers_media():
    from mio_core.connectors import ConnectorManager, ConnectorRegistry
    from mio_core.connectors.adapters import register_from_env
    mgr = ConnectorManager(ConnectorRegistry())
    summary = register_from_env(mgr, env={"OPENAI_API_KEY": "k"}, workspace="/tmp/ws")
    reg = set(summary["registered"])
    assert "ffmpeg" in reg and "openai-tts" in reg and "whisper" in reg   # media pack bağlandı


# ---- UÇTAN UCA: Presentation niyeti → Executive köprüsü → gerçek media connector (executed) ----
def test_presentation_deliver_via_media_connector(tmp_path):
    from mio_core.runtime import boot
    from mio_core import appservice
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        # gerçek OpenAI-TTS connector'ı enjekte transport ile bağla (Executive/ConnectorManager tarafı)
        tts = openai_tts_connector(api_key="sk-test",
                                   urlopen=lambda req, timeout=30: _Resp({}, 200))
        mio.connectors.register(tts)
        s = appservice.presentation_outline(mio, "Podcast", ["giriş", "içerik"], kind="podcast")
        d = appservice.presentation_deliver(mio, s["id"])
        # seslendirme niyetleri gerçek media connector ile YÜRÜTÜLDÜ
        synth = [r for r in d["results"] if r["capability"] == "speech.synthesize"]
        assert synth and all(r["outcome"]["status"] == "executed" for r in synth)
        assert d["executed"] >= 2
    finally:
        mio.close()
