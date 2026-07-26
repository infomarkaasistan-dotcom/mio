"""MIO Core · Connector adapters · bootstrap — env/config'ten YAPILANDIRILMIŞ adapter'ları bağlar.

`register_from_env(manager, env, workspace)`: hangi connector'ın bağlanacağına env belirler (.env.example ile
uyumlu). Kimlik/host eksikse o connector ATLANIR (bağlanmaz) — sistem yine çalışır (graceful). Böylece "tüm
connector'ları bağla" = mevcut yapılandırmaya göre gerçekçi bağlama; sır ASLA loglanmaz (yalnız ad döner)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from .caldav import caldav_connector
from .filesystem import filesystem_connector
from .git import git_connector
from .media import ffmpeg_connector, openai_tts_connector, piper_tts_connector, whisper_connector
from .ollama import ollama_connector
from .openai_compat import openai_connector
from .shell import shell_connector
from .smtp import smtp_connector
from .webhook import webhook_connector


def _truthy(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def register_from_env(manager, *, env: Optional[dict] = None, workspace: str = ".mio") -> dict[str, Any]:
    """Yapılandırılmış connector'ları manager'a kaydeder. Döner: {registered:[...], skipped:[...]}. Sır loglanmaz."""
    env = dict(os.environ if env is None else env)
    registered: list = []
    skipped: list = []

    # System — Filesystem (sandbox: workspace/files) her zaman; güvenli + gerçek
    fs_root = env.get("MIO_FS_ROOT") or str(Path(workspace) / "files")
    manager.register(filesystem_connector(root=fs_root)); registered.append("filesystem")

    # System — Git (health git varlığına bağlı)
    manager.register(git_connector()); registered.append("git")

    # System — Shell (yüksek-risk; yalnız açıkça etkinse — Manager Madde 24 kapısı yine yürürlükte)
    if _truthy(env.get("MIO_SHELL_ENABLED")):
        manager.register(shell_connector()); registered.append("shell")
    else:
        skipped.append("shell (MIO_SHELL_ENABLED kapalı)")

    # Communication — SMTP
    if env.get("SMTP_HOST"):
        manager.register(smtp_connector(
            host=env["SMTP_HOST"], port=int(env.get("SMTP_PORT", "587")),
            user=env.get("SMTP_USER"), password=env.get("SMTP_PASSWORD"),
            use_tls=_truthy(env.get("SMTP_TLS", "true"))))
        registered.append("smtp")
    else:
        skipped.append("smtp (SMTP_HOST yok)")

    # Communication — Webhook (Slack/Discord/Telegram/generic)
    if env.get("MIO_WEBHOOK_URL"):
        manager.register(webhook_connector(url=env["MIO_WEBHOOK_URL"],
                                           payload_style=env.get("MIO_WEBHOOK_STYLE", "slack")))
        registered.append("webhook")
    else:
        skipped.append("webhook (MIO_WEBHOOK_URL yok)")

    # AI — Ollama (yerel, anahtarsız)
    if _truthy(env.get("LLM_ENABLED")) or env.get("OLLAMA_HOST"):
        manager.register(ollama_connector(host=env.get("OLLAMA_HOST", "http://localhost:11434"),
                                          model=env.get("MIO_OLLAMA_MODEL", "llama3")))
        registered.append("ollama")
    else:
        skipped.append("ollama (LLM_ENABLED kapalı)")

    # AI — OpenAI-uyumlu (OpenAI / DeepSeek / Qwen — hepsi aynı şema)
    for provider, key_env, base in (
            ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1"),
            ("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1"),
            ("qwen", "QWEN_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1")):
        if env.get(key_env):
            manager.register(openai_connector(api_key=env[key_env], base_url=base, name=provider,
                                              model=env.get(f"{provider.upper()}_MODEL", "gpt-4o-mini")))
            registered.append(provider)
        else:
            skipped.append(f"{provider} ({key_env} yok)")

    # Productivity — CalDAV (takvim)
    if env.get("CALDAV_URL") and env.get("CALDAV_USER"):
        manager.register(caldav_connector(url=env["CALDAV_URL"], user=env["CALDAV_USER"],
                                          password=env.get("CALDAV_PASSWORD", "")))
        registered.append("caldav")
    else:
        skipped.append("caldav (CALDAV_URL/USER yok)")

    # Media — FFmpeg (yerel; health binary'ye bağlı → yoksa sağlıksız, çökmez)
    manager.register(ffmpeg_connector()); registered.append("ffmpeg")

    # Media — TTS (Piper yerel, ya da OpenAI-uyumlu bulut)
    if env.get("PIPER_MODEL"):
        manager.register(piper_tts_connector(binary=env.get("PIPER_BINARY", "piper"),
                                             model_path=env["PIPER_MODEL"]))
        registered.append("piper")
    elif env.get("OPENAI_API_KEY"):
        manager.register(openai_tts_connector(api_key=env["OPENAI_API_KEY"],
                                              voice=env.get("MIO_TTS_VOICE", "alloy")))
        registered.append("openai-tts")
    else:
        skipped.append("tts (PIPER_MODEL / OPENAI_API_KEY yok)")

    # Media — STT (Whisper-uyumlu)
    if env.get("OPENAI_API_KEY") or env.get("WHISPER_URL"):
        manager.register(whisper_connector(api_key=env.get("OPENAI_API_KEY", ""),
                                           base_url=env.get("WHISPER_URL", "https://api.openai.com/v1")))
        registered.append("whisper")
    else:
        skipped.append("whisper (OPENAI_API_KEY / WHISPER_URL yok)")

    return {"registered": registered, "skipped": skipped, "fs_root": fs_root}


__all__ = ["register_from_env"]
