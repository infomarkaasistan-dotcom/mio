"""MIO Core · Media Generation Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik ORKESTRASYON.

Üretim-iş durum makinesi + connector routing. Gerçek image/video/audio üretimi enjekte edilen generator'a
(adapter) delege; **generator yoksa no_connector** (uydurma asset YOK — Madde 8). Çekirdek model çalıştırmaz.
authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, MediaEvents, media_contract
from .models import (
    GenJob,
    JobStatus,
    MediaConfig,
    MediaKind,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import MediaRepository

logger = logging.getLogger("mio.domain.media")

Generator = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MediaGenerationDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: MediaRepository, *, bus=None,
                 config: Optional[MediaConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or MediaConfig()
        self._generators: dict[str, tuple[Generator, str]] = {}
        self._metrics = {"jobs": 0, "completed": 0, "no_connector": 0, "failed": 0}

    # ------------------------------------------------------------------ #
    def register_generator(self, kind: str, fn: Generator, *, name: str = "adapter") -> None:
        """Bir medya türü için GERÇEK üretim connector'ı bağlar (kompozisyon-zamanı DI)."""
        if kind not in MediaKind.ALL:
            raise ValidationError(f"Geçersiz medya türü: {kind}")
        self._generators[kind] = (fn, name)

    def generate(self, actor: str, kind: str, prompt: str, *,
                 params: Optional[dict] = None) -> dict[str, Any]:
        """Bir üretim işi oluşturur ve (varsa) generator'a delege eder."""
        self._authorize_writer(actor)
        if kind not in MediaKind.ALL:
            raise ValidationError(f"Geçersiz medya türü: {kind}")
        prompt = self._require(prompt, "prompt")
        if len(prompt) > self._cfg.max_prompt_len:
            raise ValidationError(f"prompt çok uzun (>{self._cfg.max_prompt_len})")
        job = GenJob(kind=kind, prompt=prompt, params=dict(params or {}), status=JobStatus.PENDING)
        self._metrics["jobs"] += 1
        self._emit(MediaEvents.JOB_CREATED, {"id": job.id, "kind": kind})

        entry = self._generators.get(kind)
        if entry is None:                       # DÜRÜST: gerçek üretim modeli bağlı değil
            job.status = JobStatus.NO_CONNECTOR
            job.finished_at = _now()
            self._repo.put_job(job)
            self._metrics["no_connector"] += 1
            self._emit(MediaEvents.NO_CONNECTOR, {"id": job.id, "kind": kind})
            return job.to_dict()

        fn, name = entry
        job.status = JobStatus.RUNNING
        job.connector = name
        try:
            result = fn({"kind": kind, "prompt": prompt, "params": job.params})
            job.status = JobStatus.COMPLETED
            job.result = dict(result or {})
            self._metrics["completed"] += 1
            self._emit(MediaEvents.JOB_COMPLETED, {"id": job.id, "connector": name})
        except Exception as exc:  # noqa: BLE001 — connector hatası işe dönüşür, sistemi bozmaz
            job.status = JobStatus.FAILED
            job.error = str(exc)[:300]
            self._metrics["failed"] += 1
            self._emit(MediaEvents.JOB_FAILED, {"id": job.id, "error": job.error})
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

    def list_jobs(self, actor: str, *, status: Optional[str] = None,
                  kind: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in JobStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        if kind is not None and kind not in MediaKind.ALL:
            raise ValidationError(f"Geçersiz tür: {kind}")
        return [j.to_dict() for j in self._repo.all_jobs(status=status, kind=kind)]

    def connectors(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"available": sorted(self._generators), "all_kinds": sorted(MediaKind.ALL),
                "missing": sorted(MediaKind.ALL - set(self._generators))}

    def stats(self) -> dict[str, Any]:
        return {"jobs": self._repo.job_count(), "connectors": len(self._generators),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return media_contract()

    # ------------------------------------------------------------------ #
    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' medya erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' medya üretimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
