"""MIO Core · Web Intelligence Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Web erişimi AĞ gerektirir → çekirdek deterministik ORKESTRASYON: fetch/crawl/search iş durum makinesi +
connector routing + deterministik domain ALLOWLIST (güvenlik). Gerçek ağ enjekte edilen fetcher'a (adapter)
delege; fetcher yoksa DÜRÜSTÇE no_connector (uydurma içerik YOK — Madde 8). Ağ çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def host_of(url: str) -> str:
    """Bir URL'in host'unu deterministik çıkarır (allowlist için)."""
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""


class WebKind:
    FETCH = "fetch"          # tek URL içeriği
    CRAWL = "crawl"          # URL'den başlayarak tarama
    SEARCH = "search"        # sorgu (host allowlist gerekmez)
    ALL = {FETCH, CRAWL, SEARCH}
    NEEDS_URL = {FETCH, CRAWL}


class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_CONNECTOR = "no_connector"
    BLOCKED = "blocked"      # allowlist ihlali (güvenlik)
    ALL = {PENDING, RUNNING, COMPLETED, FAILED, NO_CONNECTOR, BLOCKED}


class WebError(Exception):
    """Web Intelligence Domain temel hatası."""


class ValidationError(WebError):
    pass


class UnauthorizedError(WebError):
    pass


class NotFoundError(WebError):
    pass


@dataclass
class WebJob:
    kind: str
    target: str              # url veya arama sorgusu
    params: dict[str, Any] = field(default_factory=dict)
    status: str = JobStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    connector: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "target": self.target, "params": self.params,
                "status": self.status, "result": self.result, "error": self.error,
                "connector": self.connector, "created_at": self.created_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WebJob":
        return cls(kind=d["kind"], target=d["target"], params=dict(d.get("params") or {}),
                   status=d.get("status", JobStatus.PENDING), result=dict(d.get("result") or {}),
                   error=d.get("error", ""), connector=d.get("connector", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   finished_at=d.get("finished_at"))


@dataclass
class WebConfig:
    # allowlist boşsa → tüm host'lara izin; doluysa → yalnız listedeki host'lar (deterministik güvenlik)
    allowed_hosts: set = field(default_factory=set)
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Research", "Marketing", "Operations", "Knowledge",
        "Reasoning", "Planning", "Perception"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Research", "Operations"})
    admin_actors: set = field(default_factory=lambda: {"owner", "Executive", "Security", "Operations"})

    def host_allowed(self, host: str) -> bool:
        return (not self.allowed_hosts) or host in self.allowed_hosts

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_admin(self, actor: str) -> bool:
        return actor == "owner" or actor in self.admin_actors


__all__ = [
    "WebKind", "JobStatus", "WebJob", "WebConfig", "host_of",
    "WebError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
