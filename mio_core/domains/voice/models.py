"""MIO Core · Voice Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Voice gerçek STT/TTS modeli gerektirir → çekirdek deterministik ORKESTRASYON: audio asset registry + voice-iş
durum makinesi + connector routing. Gerçek transcribe/synthesize/diarize enjekte edilen analyzer'a (adapter)
delege; analyzer yoksa DÜRÜSTÇE no_connector (uydurma/placeholder YOK — Madde 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VoiceKind:
    TRANSCRIBE = "transcribe"        # STT — asset gerekir
    SYNTHESIZE = "synthesize"        # TTS — text gerekir
    DIARIZE = "diarize"              # konuşmacı ayrımı — asset gerekir
    ALL = {TRANSCRIBE, SYNTHESIZE, DIARIZE}
    NEEDS_ASSET = {TRANSCRIBE, DIARIZE}
    NEEDS_TEXT = {SYNTHESIZE}


class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_CONNECTOR = "no_connector"
    ALL = {PENDING, RUNNING, COMPLETED, FAILED, NO_CONNECTOR}


class VoiceError(Exception):
    """Voice Domain temel hatası."""


class ValidationError(VoiceError):
    pass


class UnauthorizedError(VoiceError):
    pass


class NotFoundError(VoiceError):
    pass


@dataclass
class AudioAsset:
    uri: str
    duration_sec: Optional[float] = None
    fmt: str = "wav"
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "uri": self.uri, "duration_sec": self.duration_sec, "fmt": self.fmt,
                "description": self.description, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AudioAsset":
        return cls(uri=d["uri"], duration_sec=d.get("duration_sec"), fmt=d.get("fmt", "wav"),
                   description=d.get("description", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class VoiceJob:
    kind: str
    asset_id: str = ""
    text: str = ""
    status: str = JobStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    connector: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "asset_id": self.asset_id, "text": self.text,
                "status": self.status, "result": self.result, "error": self.error,
                "connector": self.connector, "created_at": self.created_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VoiceJob":
        return cls(kind=d["kind"], asset_id=d.get("asset_id", ""), text=d.get("text", ""),
                   status=d.get("status", JobStatus.PENDING), result=dict(d.get("result") or {}),
                   error=d.get("error", ""), connector=d.get("connector", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   finished_at=d.get("finished_at"))


@dataclass
class VoiceConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Communication", "Perception", "Operations", "Marketing",
        "Research", "Reasoning", "Planning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Communication", "Perception", "Operations"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "VoiceKind", "JobStatus", "AudioAsset", "VoiceJob", "VoiceConfig",
    "VoiceError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
