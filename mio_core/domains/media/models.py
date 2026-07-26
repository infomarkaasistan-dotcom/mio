"""MIO Core · Media Generation Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Medya üretimi gerçek MODEL gerektirir → çekirdek deterministik ORKESTRASYON: üretim-iş durum makinesi +
connector routing. Gerçek image/video/audio üretimi enjekte edilen generator'a (adapter) delege; generator
yoksa DÜRÜSTÇE no_connector (uydurma asset YOK — Madde 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MediaKind:
    IMAGE_GEN = "image_gen"
    VIDEO_GEN = "video_gen"
    AUDIO_GEN = "audio_gen"
    ALL = {IMAGE_GEN, VIDEO_GEN, AUDIO_GEN}


class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_CONNECTOR = "no_connector"
    ALL = {PENDING, RUNNING, COMPLETED, FAILED, NO_CONNECTOR}


class MediaError(Exception):
    """Media Generation Domain temel hatası."""


class ValidationError(MediaError):
    pass


class UnauthorizedError(MediaError):
    pass


class NotFoundError(MediaError):
    pass


@dataclass
class GenJob:
    kind: str
    prompt: str
    params: dict[str, Any] = field(default_factory=dict)
    status: str = JobStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)   # üretilen asset (uri/metadata)
    error: str = ""
    connector: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "prompt": self.prompt, "params": self.params,
                "status": self.status, "result": self.result, "error": self.error,
                "connector": self.connector, "created_at": self.created_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GenJob":
        return cls(kind=d["kind"], prompt=d["prompt"], params=dict(d.get("params") or {}),
                   status=d.get("status", JobStatus.PENDING), result=dict(d.get("result") or {}),
                   error=d.get("error", ""), connector=d.get("connector", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   finished_at=d.get("finished_at"))


@dataclass
class MediaConfig:
    max_prompt_len: int = 4000
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Marketing", "Communication", "Operations", "Product",
        "Research", "Reasoning", "Planning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Marketing", "Communication", "Operations"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "MediaKind", "JobStatus", "GenJob", "MediaConfig",
    "MediaError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
