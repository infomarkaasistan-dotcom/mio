"""MIO Core · Media Generation — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import GenJob

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gen_job (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_genjob_status ON gen_job(status);
CREATE INDEX IF NOT EXISTS ix_genjob_kind ON gen_job(kind);
"""


class MediaRepository:
    def __init__(self, path: str = "mio_media.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put_job(self, j: GenJob) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO gen_job (id, kind, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (j.id, j.kind, j.status, json.dumps(j.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_job(self, job_id: str) -> Optional[GenJob]:
        r = self._conn.execute("SELECT data FROM gen_job WHERE id=?", (job_id,)).fetchone()
        return GenJob.from_dict(json.loads(r["data"])) if r else None

    def all_jobs(self, *, status: Optional[str] = None, kind: Optional[str] = None) -> list[GenJob]:
        q, args, conds = "SELECT data FROM gen_job", [], []
        if status:
            conds.append("status=?"); args.append(status)
        if kind:
            conds.append("kind=?"); args.append(kind)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY rowid"
        return [GenJob.from_dict(json.loads(r["data"])) for r in self._conn.execute(q, args).fetchall()]

    def job_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM gen_job WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM gen_job").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["MediaRepository"]
