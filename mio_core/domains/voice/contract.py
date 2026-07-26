"""MIO Core · Voice Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class VoiceEvents:
    ASSET_REGISTERED = "voice.asset_registered"
    JOB_CREATED = "voice.job_created"
    JOB_COMPLETED = "voice.job_completed"
    JOB_FAILED = "voice.job_failed"
    NO_CONNECTOR = "voice.no_connector"


OPERATIONS = ("register_asset", "transcribe", "synthesize", "diarize", "get_job", "list_jobs",
              "connectors", "stats")


def voice_contract() -> dict[str, Any]:
    return {
        "domain": "voice",
        "version": CONTRACT_VERSION,
        "description": "Deterministik voice ORKESTRASYONU: audio asset + voice-iş durum makinesi + connector "
                       "routing. Gerçek STT/TTS adapter'a delege; adapter yoksa DÜRÜSTÇE no_connector.",
        "operations": list(OPERATIONS),
        "events": [VoiceEvents.ASSET_REGISTERED, VoiceEvents.JOB_CREATED, VoiceEvents.JOB_COMPLETED,
                   VoiceEvents.JOB_FAILED, VoiceEvents.NO_CONNECTOR],
        "voice_kinds": ["transcribe", "synthesize", "diarize"],
        "job_statuses": ["pending", "running", "completed", "failed", "no_connector"],
        "invariants": ["gerçek STT/TTS adapter'a delege edilir (çekirdek model çalıştırmaz)",
                       "analyzer yoksa no_connector (uydurma sonuç YOK — Madde 8)",
                       "durum makinesi ve routing deterministiktir"],
    }
