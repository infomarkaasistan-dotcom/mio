"""MIO Core · Vision Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Asset, VisionJob

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vision_asset (
    id TEXT PRIMARY KEY, uri TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vision_job (
    id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, analysis TEXT NOT NULL, status TEXT NOT NULL,
    data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_vjob_asset ON vision_job(asset_id);
CREATE INDEX IF NOT EXISTS ix_vjob_status ON vision_job(status);
"""


class VisionRepository:
    def __init__(self, path: str = "mio_vision.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- assets ---------------------------------------------------------- #
    def put_asset(self, a: Asset) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO vision_asset (id, uri, kind, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET uri=excluded.uri, kind=excluded.kind, data=excluded.data",
                (a.id, a.uri, a.kind, json.dumps(a.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_asset(self, asset_id: str) -> Optional[Asset]:
        r = self._conn.execute("SELECT data FROM vision_asset WHERE id=?", (asset_id,)).fetchone()
        return Asset.from_dict(json.loads(r["data"])) if r else None

    def all_assets(self) -> list[Asset]:
        rows = self._conn.execute("SELECT data FROM vision_asset ORDER BY rowid").fetchall()
        return [Asset.from_dict(json.loads(r["data"])) for r in rows]

    def asset_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM vision_asset").fetchone()["c"]

    # -- jobs ------------------------------------------------------------ #
    def put_job(self, j: VisionJob) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO vision_job (id, asset_id, analysis, status, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (j.id, j.asset_id, j.analysis, j.status, json.dumps(j.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_job(self, job_id: str) -> Optional[VisionJob]:
        r = self._conn.execute("SELECT data FROM vision_job WHERE id=?", (job_id,)).fetchone()
        return VisionJob.from_dict(json.loads(r["data"])) if r else None

    def all_jobs(self, *, status: Optional[str] = None) -> list[VisionJob]:
        if status:
            rows = self._conn.execute("SELECT data FROM vision_job WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM vision_job ORDER BY rowid").fetchall()
        return [VisionJob.from_dict(json.loads(r["data"])) for r in rows]

    def job_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM vision_job WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM vision_job").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["VisionRepository"]
