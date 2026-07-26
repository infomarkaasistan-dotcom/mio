"""MIO Core · Web Intelligence Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik ORKESTRASYON.

fetch/crawl/search iş durum makinesi + connector routing + domain ALLOWLIST güvenliği. Gerçek ağ enjekte
edilen fetcher'a (adapter) delege; **fetcher yoksa no_connector** (uydurma içerik YOK — Madde 8). Ağ çekirdekte
YOK. authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, WebEvents, web_contract
from .models import (
    JobStatus,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    WebConfig,
    WebJob,
    WebKind,
    host_of,
)
from .repository import WebRepository

logger = logging.getLogger("mio.domain.web_intelligence")

Fetcher = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WebIntelligenceDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: WebRepository, *, bus=None,
                 config: Optional[WebConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or WebConfig()
        self._fetchers: dict[str, tuple[Fetcher, str]] = {}
        self._metrics = {"jobs": 0, "completed": 0, "no_connector": 0, "failed": 0, "blocked": 0}

    # ------------------------------------------------------------------ #
    def register_fetcher(self, kind: str, fn: Fetcher, *, name: str = "adapter") -> None:
        """Bir web türü için GERÇEK ağ connector'ı bağlar (kompozisyon-zamanı DI)."""
        if kind not in WebKind.ALL:
            raise ValidationError(f"Geçersiz web türü: {kind}")
        self._fetchers[kind] = (fn, name)

    def allow_host(self, actor: str, host: str) -> dict[str, Any]:
        """Allowlist'e host ekler (admin). Allowlist doluysa yalnız izinliler erişilebilir."""
        if not self._cfg.is_admin(actor):
            raise UnauthorizedError(f"'{actor}' allowlist yönetimi için yetkili değil (admin gerekir)")
        host = self._require(host, "host").lower()
        self._cfg.allowed_hosts.add(host)
        return {"allowed_hosts": sorted(self._cfg.allowed_hosts)}

    def fetch(self, actor: str, url: str) -> dict[str, Any]:
        return self._run(actor, WebKind.FETCH, url)

    def crawl(self, actor: str, url: str, *, depth: int = 1) -> dict[str, Any]:
        return self._run(actor, WebKind.CRAWL, url, params={"depth": int(depth)})

    def search(self, actor: str, query: str) -> dict[str, Any]:
        return self._run(actor, WebKind.SEARCH, query)

    # ------------------------------------------------------------------ #
    def _run(self, actor: str, kind: str, target: str, *,
             params: Optional[dict] = None) -> dict[str, Any]:
        self._authorize_writer(actor)
        target = self._require(target, "hedef (url/sorgu)")
        job = WebJob(kind=kind, target=target, params=dict(params or {}), status=JobStatus.PENDING)
        self._metrics["jobs"] += 1
        self._emit(WebEvents.JOB_CREATED, {"id": job.id, "kind": kind})

        # Güvenlik: URL gerektiren türlerde allowlist kontrolü (deterministik)
        if kind in WebKind.NEEDS_URL:
            host = host_of(target)
            if not host:
                return self._finish(job, JobStatus.FAILED, error="geçersiz URL (host yok)")
            if not self._cfg.host_allowed(host):
                self._metrics["blocked"] += 1
                self._emit(WebEvents.BLOCKED, {"id": job.id, "host": host})
                return self._finish(job, JobStatus.BLOCKED,
                                    error=f"host allowlist'te değil: {host}")

        entry = self._fetchers.get(kind)
        if entry is None:                       # DÜRÜST: gerçek ağ connector'ı bağlı değil
            self._metrics["no_connector"] += 1
            self._emit(WebEvents.NO_CONNECTOR, {"id": job.id, "kind": kind})
            return self._finish(job, JobStatus.NO_CONNECTOR)

        fn, name = entry
        job.connector = name
        job.status = JobStatus.RUNNING
        try:
            result = fn({"kind": kind, "target": target, "params": job.params})
            self._metrics["completed"] += 1
            self._emit(WebEvents.JOB_COMPLETED, {"id": job.id, "connector": name})
            return self._finish(job, JobStatus.COMPLETED, result=dict(result or {}))
        except Exception as exc:  # noqa: BLE001 — connector hatası işe dönüşür, sistemi bozmaz
            self._metrics["failed"] += 1
            self._emit(WebEvents.JOB_FAILED, {"id": job.id, "error": str(exc)[:200]})
            return self._finish(job, JobStatus.FAILED, error=str(exc)[:300])

    def _finish(self, job: WebJob, status: str, *, result: Optional[dict] = None,
                error: str = "") -> dict[str, Any]:
        job.status = status
        job.result = result or {}
        job.error = error
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
        return {"available": sorted(self._fetchers), "all_kinds": sorted(WebKind.ALL),
                "missing": sorted(WebKind.ALL - set(self._fetchers)),
                "allowed_hosts": sorted(self._cfg.allowed_hosts) or "all"}

    def stats(self) -> dict[str, Any]:
        return {"jobs": self._repo.job_count(), "connectors": len(self._fetchers),
                "allowed_hosts": len(self._cfg.allowed_hosts), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return web_contract()

    # ------------------------------------------------------------------ #
    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' web erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' web işi başlatmak için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
