"""MIO Core · Web Intelligence Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class WebEvents:
    JOB_CREATED = "web.job_created"
    JOB_COMPLETED = "web.job_completed"
    JOB_FAILED = "web.job_failed"
    NO_CONNECTOR = "web.no_connector"
    BLOCKED = "web.blocked"          # allowlist ihlali


OPERATIONS = ("fetch", "crawl", "search", "allow_host", "get_job", "list_jobs", "connectors", "stats")


def web_contract() -> dict[str, Any]:
    return {
        "domain": "web_intelligence",
        "version": CONTRACT_VERSION,
        "description": "Deterministik web ORKESTRASYONU: fetch/crawl/search iş durum makinesi + connector "
                       "routing + domain allowlist güvenliği. Gerçek ağ adapter'a delege; yoksa no_connector.",
        "operations": list(OPERATIONS),
        "events": [WebEvents.JOB_CREATED, WebEvents.JOB_COMPLETED, WebEvents.JOB_FAILED,
                   WebEvents.NO_CONNECTOR, WebEvents.BLOCKED],
        "web_kinds": ["fetch", "crawl", "search"],
        "job_statuses": ["pending", "running", "completed", "failed", "no_connector", "blocked"],
        "invariants": ["gerçek ağ adapter'a delege edilir (çekirdek ağ yapmaz)",
                       "fetcher yoksa no_connector (uydurma içerik YOK — Madde 8)",
                       "allowlist doluysa yalnız izinli host'lara erişilir (deterministik güvenlik)"],
    }
