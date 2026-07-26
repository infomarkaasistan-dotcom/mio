"""MIO Core · Voice Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import AudioAsset, VoiceJob

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audio_asset (
    id TEXT PRIMARY KEY, uri TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS voice_job (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_voicejob_status ON voice_job(status);
"""


class VoiceRepository:
    def __init__(self, path: str = "mio_voice.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put_asset(self, a: AudioAsset) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audio_asset (id, uri, data) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET uri=excluded.uri, data=excluded.data",
                (a.id, a.uri, json.dumps(a.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_asset(self, asset_id: str) -> Optional[AudioAsset]:
        r = self._conn.execute("SELECT data FROM audio_asset WHERE id=?", (asset_id,)).fetchone()
        return AudioAsset.from_dict(json.loads(r["data"])) if r else None

    def all_assets(self) -> list[AudioAsset]:
        rows = self._conn.execute("SELECT data FROM audio_asset ORDER BY rowid").fetchall()
        return [AudioAsset.from_dict(json.loads(r["data"])) for r in rows]

    def asset_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM audio_asset").fetchone()["c"]

    def put_job(self, j: VoiceJob) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO voice_job (id, kind, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (j.id, j.kind, j.status, json.dumps(j.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_job(self, job_id: str) -> Optional[VoiceJob]:
        r = self._conn.execute("SELECT data FROM voice_job WHERE id=?", (job_id,)).fetchone()
        return VoiceJob.from_dict(json.loads(r["data"])) if r else None

    def all_jobs(self, *, status: Optional[str] = None) -> list[VoiceJob]:
        if status:
            rows = self._conn.execute("SELECT data FROM voice_job WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM voice_job ORDER BY rowid").fetchall()
        return [VoiceJob.from_dict(json.loads(r["data"])) for r in rows]

    def job_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM voice_job WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM voice_job").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["VoiceRepository"]
