"""MIO Core · Voice Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik ORKESTRASYON.

Audio asset registry + voice-iş durum makinesi + connector routing. Gerçek STT/TTS enjekte edilen analyzer'a
(adapter) delege; **analyzer yoksa no_connector** (uydurma sonuç YOK — Madde 8). Çekirdek model çalıştırmaz.
authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, VoiceEvents, voice_contract
from .models import (
    AudioAsset,
    JobStatus,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    VoiceConfig,
    VoiceJob,
    VoiceKind,
)
from .repository import VoiceRepository

logger = logging.getLogger("mio.domain.voice")

Analyzer = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VoiceDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: VoiceRepository, *, bus=None,
                 config: Optional[VoiceConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or VoiceConfig()
        self._analyzers: dict[str, tuple[Analyzer, str]] = {}
        self._metrics = {"assets": 0, "jobs": 0, "completed": 0, "no_connector": 0, "failed": 0}

    # ------------------------------------------------------------------ #
    def register_analyzer(self, kind: str, fn: Analyzer, *, name: str = "adapter") -> None:
        """Bir voice türü için GERÇEK connector (STT/TTS adapter) bağlar (kompozisyon-zamanı DI)."""
        if kind not in VoiceKind.ALL:
            raise ValidationError(f"Geçersiz voice türü: {kind}")
        self._analyzers[kind] = (fn, name)

    def register_asset(self, actor: str, uri: str, *, duration_sec: Optional[float] = None,
                       fmt: str = "wav", description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        uri = self._require(uri, "audio uri")
        a = AudioAsset(uri=uri, duration_sec=duration_sec, fmt=fmt, description=description)
        self._repo.put_asset(a)
        self._metrics["assets"] += 1
        self._emit(VoiceEvents.ASSET_REGISTERED, {"actor": actor, "id": a.id})
        return a.to_dict()

    def transcribe(self, actor: str, asset_id: str) -> dict[str, Any]:
        return self._run(actor, VoiceKind.TRANSCRIBE, asset_id=asset_id)

    def diarize(self, actor: str, asset_id: str) -> dict[str, Any]:
        return self._run(actor, VoiceKind.DIARIZE, asset_id=asset_id)

    def synthesize(self, actor: str, text: str) -> dict[str, Any]:
        return self._run(actor, VoiceKind.SYNTHESIZE, text=text)

    # ------------------------------------------------------------------ #
    def _run(self, actor: str, kind: str, *, asset_id: str = "", text: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        asset = None
        if kind in VoiceKind.NEEDS_ASSET:
            asset = self._repo.get_asset(asset_id)
            if asset is None:
                raise NotFoundError(f"Audio asset bulunamadı: {asset_id}")
        if kind in VoiceKind.NEEDS_TEXT:
            text = self._require(text, "metin (synthesize)")
        job = VoiceJob(kind=kind, asset_id=asset_id, text=text, status=JobStatus.PENDING)
        self._metrics["jobs"] += 1
        self._emit(VoiceEvents.JOB_CREATED, {"id": job.id, "kind": kind})

        entry = self._analyzers.get(kind)
        if entry is None:                       # DÜRÜST: gerçek STT/TTS bağlı değil
            job.status = JobStatus.NO_CONNECTOR
            job.finished_at = _now()
            self._repo.put_job(job)
            self._metrics["no_connector"] += 1
            self._emit(VoiceEvents.NO_CONNECTOR, {"id": job.id, "kind": kind})
            return job.to_dict()

        fn, name = entry
        job.status = JobStatus.RUNNING
        job.connector = name
        try:
            result = fn({"kind": kind, "asset": asset.to_dict() if asset else None, "text": text})
            job.status = JobStatus.COMPLETED
            job.result = dict(result or {})
            self._metrics["completed"] += 1
            self._emit(VoiceEvents.JOB_COMPLETED, {"id": job.id, "connector": name})
        except Exception as exc:  # noqa: BLE001 — connector hatası işe dönüşür, sistemi bozmaz
            job.status = JobStatus.FAILED
            job.error = str(exc)[:300]
            self._metrics["failed"] += 1
            self._emit(VoiceEvents.JOB_FAILED, {"id": job.id, "error": job.error})
        job.finished_at = _now()
        self._repo.put_job(job)
        return job.to_dict()

    # ------------------------------------------------------------------ #
    def get_job(self, actor: str, job_id: str) -> dict[str, Any]:
        self._authorize(actor)
        j = self._repo.get_job(job_id)
        if j is None:
            raise NotFoundError(f"İş bulunamadı: {job_id}")
        return j.to_dict()

    def list_jobs(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in JobStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [j.to_dict() for j in self._repo.all_jobs(status=status)]

    def connectors(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"available": sorted(self._analyzers), "all_kinds": sorted(VoiceKind.ALL),
                "missing": sorted(VoiceKind.ALL - set(self._analyzers))}

    def stats(self) -> dict[str, Any]:
        return {"assets": self._repo.asset_count(), "jobs": self._repo.job_count(),
                "connectors": len(self._analyzers), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return voice_contract()

    # ------------------------------------------------------------------ #
    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' voice erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' voice yazımı için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
