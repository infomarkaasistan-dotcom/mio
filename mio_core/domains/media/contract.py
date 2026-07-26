"""MIO Core · Media Generation Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class MediaEvents:
    JOB_CREATED = "media.job_created"
    JOB_COMPLETED = "media.job_completed"
    JOB_FAILED = "media.job_failed"
    NO_CONNECTOR = "media.no_connector"


OPERATIONS = ("generate", "get_job", "list_jobs", "connectors", "stats")


def media_contract() -> dict[str, Any]:
    return {
        "domain": "media_generation",
        "version": CONTRACT_VERSION,
        "description": "Deterministik medya üretim ORKESTRASYONU: üretim-iş durum makinesi + connector routing. "
                       "Gerçek image/video/audio üretimi adapter'a delege; adapter yoksa DÜRÜSTÇE no_connector.",
        "operations": list(OPERATIONS),
        "events": [MediaEvents.JOB_CREATED, MediaEvents.JOB_COMPLETED, MediaEvents.JOB_FAILED,
                   MediaEvents.NO_CONNECTOR],
        "media_kinds": ["image_gen", "video_gen", "audio_gen"],
        "job_statuses": ["pending", "running", "completed", "failed", "no_connector"],
        "invariants": ["gerçek üretim modeli adapter'a delege edilir (çekirdek model çalıştırmaz)",
                       "generator yoksa no_connector (uydurma asset YOK — Madde 8)",
                       "durum makinesi ve routing deterministiktir"],
    }
