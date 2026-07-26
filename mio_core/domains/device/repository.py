"""MIO Core · Device Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import CommandJob, Device

_SCHEMA = """
CREATE TABLE IF NOT EXISTS device (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS command_job (
    id TEXT PRIMARY KEY, device_id TEXT NOT NULL, status TEXT NOT NULL, risk TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_cmdjob_status ON command_job(status);
"""


class DeviceRepository:
    def __init__(self, path: str = "mio_device.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- devices --------------------------------------------------------- #
    def put_device(self, d: Device) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO device (id, name, kind, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, kind=excluded.kind, data=excluded.data",
                (d.id, d.name, d.kind, json.dumps(d.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_device(self, device_id: str) -> Optional[Device]:
        r = self._conn.execute("SELECT data FROM device WHERE id=?", (device_id,)).fetchone()
        return Device.from_dict(json.loads(r["data"])) if r else None

    def all_devices(self) -> list[Device]:
        rows = self._conn.execute("SELECT data FROM device ORDER BY rowid").fetchall()
        return [Device.from_dict(json.loads(r["data"])) for r in rows]

    def device_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM device").fetchone()["c"]

    # -- jobs ------------------------------------------------------------ #
    def put_job(self, j: CommandJob) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO command_job (id, device_id, status, risk, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (j.id, j.device_id, j.status, j.risk, json.dumps(j.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_job(self, job_id: str) -> Optional[CommandJob]:
        r = self._conn.execute("SELECT data FROM command_job WHERE id=?", (job_id,)).fetchone()
        return CommandJob.from_dict(json.loads(r["data"])) if r else None

    def all_jobs(self, *, status: Optional[str] = None) -> list[CommandJob]:
        if status:
            rows = self._conn.execute("SELECT data FROM command_job WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM command_job ORDER BY rowid").fetchall()
        return [CommandJob.from_dict(json.loads(r["data"])) for r in rows]

    def job_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM command_job WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM command_job").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["DeviceRepository"]
