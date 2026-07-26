"""MIO Core · Scheduler Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

Koşu (run) kayıtlarını tutar: denetim + zombie-guard (çökmüş süreçten kalan 'running' koşular toparlanır)."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import RunStatus, ScheduleRun

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schedule_run (
    id TEXT PRIMARY KEY, job TEXT NOT NULL, tick INTEGER NOT NULL, status TEXT NOT NULL,
    started_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_run_job ON schedule_run(job);
CREATE INDEX IF NOT EXISTS ix_run_status ON schedule_run(status);
"""


class ScheduleRepository:
    def __init__(self, path: str = "mio_scheduler.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, run: ScheduleRun) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO schedule_run (id, job, tick, status, started_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
                "data=excluded.data",
                (run.id, run.job, run.tick, run.status, run.started_at,
                 json.dumps(run.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, run_id: str) -> Optional[ScheduleRun]:
        r = self._conn.execute("SELECT data FROM schedule_run WHERE id=?", (run_id,)).fetchone()
        return ScheduleRun.from_dict(json.loads(r["data"])) if r else None

    def recent(self, limit: int = 200, *, job: Optional[str] = None) -> list[ScheduleRun]:
        if job:
            rows = self._conn.execute("SELECT data FROM schedule_run WHERE job=? ORDER BY rowid DESC LIMIT ?",
                                      (job, limit)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM schedule_run ORDER BY rowid DESC LIMIT ?",
                                      (limit,)).fetchall()
        return [ScheduleRun.from_dict(json.loads(r["data"])) for r in rows]

    def list_by_status(self, status: str) -> list[ScheduleRun]:
        rows = self._conn.execute("SELECT data FROM schedule_run WHERE status=? ORDER BY rowid",
                                  (status,)).fetchall()
        return [ScheduleRun.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM schedule_run WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM schedule_run").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["ScheduleRepository", "RunStatus"]
