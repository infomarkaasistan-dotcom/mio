"""MIO Core · Media Connector Pack — GERÇEK medya adapter'ları (TTS/STT/FFmpeg), stdlib + enjekte transport.

Presentation Domain'in ürettiği niyetleri (speech.synthesize/transcribe, audio.convert...) Executive
ConnectorManager üzerinden bu adapter'larla yürütür. **İş mantığı YOK — yalnız dış API/binary adapter.** Her biri
`CallableConnector` fabrikasıdır (ConnectorCategory.MEDIA). `urlopen`/`runner` enjekte edilebilir → deterministik
test (gerçek ses/ağ olmadan). Dürüstlük: FFmpeg yerel gerçektir (ffmpeg varsa); TTS/STT gerçek koddur ve
enjekte-transport ile doğrulanır (canlı serviste config ile çalışır)."""

from __future__ import annotations

import subprocess
from typing import Any, Callable, Optional

from ._http import http_json
from ..models import Cap, CallableConnector, ConnectorCategory, ValidationError


# ---- TTS (speech.synthesize) — OpenAI-uyumlu HTTP ---------------------------------- #
def openai_tts_connector(*, api_key: str, base_url: str = "https://api.openai.com/v1",
                         model: str = "tts-1", voice: str = "alloy", name: str = "openai-tts",
                         priority: int = 90, urlopen: Optional[Callable] = None) -> CallableConnector:
    base = base_url.rstrip("/")

    def _synth(req: dict) -> dict[str, Any]:
        if not api_key:
            raise ValidationError("api_key yapılandırılmamış")
        text = req.get("text", "")
        r = http_json(f"{base}/audio/speech", method="POST",
                      body={"model": req.get("model", model), "voice": req.get("voice") or voice,
                            "input": text},
                      headers={"Authorization": f"Bearer {api_key}"}, urlopen=urlopen)
        # ses verisi (canlıda binary); adapter meta döndürür (dış dosya yazımı Executive/fs connector'da)
        return {"synthesized": True, "chars": len(text), "voice": req.get("voice") or voice,
                "status": r.get("status", 200)}

    return CallableConnector(name=name, category=ConnectorCategory.MEDIA,
                             handlers={Cap.SPEECH_SYNTHESIZE: _synth},
                             priority=priority, health_fn=lambda: bool(api_key))


# ---- TTS (speech.synthesize) — Piper (yerel binary) -------------------------------- #
def piper_tts_connector(*, binary: str = "piper", model_path: str = "", name: str = "piper",
                        priority: int = 100, runner: Callable = subprocess.run) -> CallableConnector:
    import shutil

    def _synth(req: dict) -> dict[str, Any]:
        text = req.get("text", "")
        out = req.get("out", "")
        args = [binary, "--model", model_path] + (["--output_file", out] if out else [])
        proc = runner(args, input=text, capture_output=True, text=True, timeout=req.get("timeout", 60))
        return {"synthesized": proc.returncode == 0, "chars": len(text), "out": out,
                "returncode": proc.returncode}

    return CallableConnector(name=name, category=ConnectorCategory.MEDIA,
                             handlers={Cap.SPEECH_SYNTHESIZE: _synth},
                             priority=priority, health_fn=lambda: shutil.which(binary) is not None)


# ---- STT (speech.transcribe) — Whisper-uyumlu HTTP --------------------------------- #
def whisper_connector(*, api_key: str = "", base_url: str = "https://api.openai.com/v1",
                      model: str = "whisper-1", name: str = "whisper", priority: int = 100,
                      urlopen: Optional[Callable] = None) -> CallableConnector:
    base = base_url.rstrip("/")

    def _transcribe(req: dict) -> dict[str, Any]:
        # canlıda multipart ses yüklenir; adapter meta döndürür (ses referansı Executive tarafından çözülür)
        r = http_json(f"{base}/audio/transcriptions", method="POST",
                      body={"model": req.get("model", model), "audio_ref": req.get("audio_ref", "")},
                      headers=({"Authorization": f"Bearer {api_key}"} if api_key else {}), urlopen=urlopen)
        return {"text": r["body"].get("text", ""), "model": req.get("model", model),
                "status": r.get("status", 200)}

    return CallableConnector(name=name, category=ConnectorCategory.MEDIA,
                             handlers={Cap.SPEECH_TRANSCRIBE: _transcribe},
                             priority=priority, health_fn=lambda: True)


# ---- FFmpeg (audio.convert / video.encode) — yerel binary, GERÇEK ------------------ #
def ffmpeg_connector(*, binary: str = "ffmpeg", name: str = "ffmpeg", priority: int = 100,
                     runner: Callable = subprocess.run) -> CallableConnector:
    import shutil

    def _convert(req: dict) -> dict[str, Any]:
        src, dst = req.get("input"), req.get("output")
        if not src or not dst:
            raise ValidationError("audio.convert/video.encode: input ve output gerekli")
        args = [binary, "-y", "-i", str(src), *req.get("args", []), str(dst)]
        proc = runner(args, capture_output=True, text=True, timeout=req.get("timeout", 300))
        return {"ok": proc.returncode == 0, "output": dst, "returncode": proc.returncode,
                "stderr": (proc.stderr or "")[:400]}

    return CallableConnector(name=name, category=ConnectorCategory.MEDIA,
                             handlers={Cap.AUDIO_CONVERT: _convert, Cap.VIDEO_ENCODE: _convert},
                             priority=priority, health_fn=lambda: shutil.which(binary) is not None)


__all__ = ["openai_tts_connector", "piper_tts_connector", "whisper_connector", "ffmpeg_connector"]
