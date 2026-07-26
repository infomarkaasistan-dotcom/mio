"""MIO Core · Web Intelligence — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import WebJob

_SCHEMA = """
CREATE TABLE IF NOT EXISTS web_job (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_webjob_status ON web_job(status);
"""


class WebRepository:
    def __init__(self, path: str = "mio_web.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put_job(self, j: WebJob) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO web_job (id, kind, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (j.id, j.kind, j.status, json.dumps(j.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_job(self, job_id: str) -> Optional[WebJob]:
        r = self._conn.execute("SELECT data FROM web_job WHERE id=?", (job_id,)).fetchone()
        return WebJob.from_dict(json.loads(r["data"])) if r else None

    def all_jobs(self, *, status: Optional[str] = None) -> list[WebJob]:
        if status:
            rows = self._conn.execute("SELECT data FROM web_job WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM web_job ORDER BY rowid").fetchall()
        return [WebJob.from_dict(json.loads(r["data"])) for r in rows]

    def job_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM web_job WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM web_job").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["WebRepository"]
