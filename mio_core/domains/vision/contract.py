"""MIO Core · Vision Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class VisionEvents:
    ASSET_REGISTERED = "vision.asset_registered"
    JOB_CREATED = "vision.job_created"
    JOB_COMPLETED = "vision.job_completed"
    JOB_FAILED = "vision.job_failed"
    NO_CONNECTOR = "vision.no_connector"


OPERATIONS = ("register_asset", "analyze", "get_job", "list_jobs", "list_assets", "connectors", "stats")


def vision_contract() -> dict[str, Any]:
    return {
        "domain": "vision",
        "version": CONTRACT_VERSION,
        "description": "Deterministik vision ORKESTRASYONU: asset registry + analiz-işi durum makinesi + "
                       "connector routing. Gerçek analiz adapter'a delege; adapter yoksa DÜRÜSTÇE no_connector.",
        "operations": list(OPERATIONS),
        "events": [VisionEvents.ASSET_REGISTERED, VisionEvents.JOB_CREATED, VisionEvents.JOB_COMPLETED,
                   VisionEvents.JOB_FAILED, VisionEvents.NO_CONNECTOR],
        "analysis_kinds": ["ocr", "object_detection", "classification", "caption"],
        "job_statuses": ["pending", "running", "completed", "failed", "no_connector"],
        "invariants": ["gerçek vision adapter'a delege edilir (çekirdek model çalıştırmaz)",
                       "analyzer yoksa no_connector (uydurma sonuç YOK — Madde 8)",
                       "durum makinesi ve routing deterministiktir"],
    }
