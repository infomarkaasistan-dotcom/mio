"""MIO Core · Vision Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Vision gerçek MODEL/donanım gerektirir → çekirdek deterministik bir ORKESTRASYON katmanıdır: asset registry +
analiz-işi durum makinesi + connector (adapter) routing. Gerçek OCR/nesne-tanıma enjekte edilen analyzer'a
delege edilir; analyzer yoksa DÜRÜSTÇE 'no_connector' döner (uydurma/placeholder YOK — Anayasa Madde 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisKind:
    OCR = "ocr"
    OBJECT_DETECTION = "object_detection"
    CLASSIFICATION = "classification"
    CAPTION = "caption"
    ALL = {OCR, OBJECT_DETECTION, CLASSIFICATION, CAPTION}


class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_CONNECTOR = "no_connector"        # gerçek analyzer bağlı değil (dürüst)
    ALL = {PENDING, RUNNING, COMPLETED, FAILED, NO_CONNECTOR}


class VisionError(Exception):
    """Vision Domain temel hatası."""


class ValidationError(VisionError):
    pass


class UnauthorizedError(VisionError):
    pass


class NotFoundError(VisionError):
    pass


@dataclass
class Asset:
    uri: str
    kind: str = "image"
    width: Optional[int] = None
    height: Optional[int] = None
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "uri": self.uri, "kind": self.kind, "width": self.width,
                "height": self.height, "description": self.description, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Asset":
        return cls(uri=d["uri"], kind=d.get("kind", "image"), width=d.get("width"), height=d.get("height"),
                   description=d.get("description", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class VisionJob:
    asset_id: str
    analysis: str
    status: str = JobStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    connector: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "asset_id": self.asset_id, "analysis": self.analysis, "status": self.status,
                "result": self.result, "error": self.error, "connector": self.connector,
                "created_at": self.created_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VisionJob":
        return cls(asset_id=d["asset_id"], analysis=d["analysis"], status=d.get("status", JobStatus.PENDING),
                   result=dict(d.get("result") or {}), error=d.get("error", ""),
                   connector=d.get("connector", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), finished_at=d.get("finished_at"))


@dataclass
class VisionConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Perception", "Operations", "Marketing", "Research",
        "Communication", "Reasoning", "Planning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Perception", "Operations", "Marketing"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "AnalysisKind", "JobStatus", "Asset", "VisionJob", "VisionConfig",
    "VisionError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
