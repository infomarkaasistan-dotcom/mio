"""MIO Core · Perception Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Percept

_SCHEMA = """
CREATE TABLE IF NOT EXISTS percept (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, source TEXT NOT NULL DEFAULT '',
    salience REAL NOT NULL DEFAULT 0.5, at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_percept_kind ON percept(kind);
CREATE INDEX IF NOT EXISTS ix_percept_salience ON percept(salience);
"""


class PerceptionRepository:
    def __init__(self, path: str = "mio_perception.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, p: Percept) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO percept (id, kind, source, salience, at, data) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, source=excluded.source, "
                "salience=excluded.salience, data=excluded.data",
                (p.id, p.kind, p.source, p.salience, p.at, json.dumps(p.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, percept_id: str) -> Optional[Percept]:
        r = self._conn.execute("SELECT data FROM percept WHERE id=?", (percept_id,)).fetchone()
        return Percept.from_dict(json.loads(r["data"])) if r else None

    def recent(self, limit: int = 100, *, kind: Optional[str] = None) -> list[Percept]:
        if kind:
            rows = self._conn.execute("SELECT data FROM percept WHERE kind=? ORDER BY rowid DESC LIMIT ?",
                                      (kind, limit)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM percept ORDER BY rowid DESC LIMIT ?",
                                      (limit,)).fetchall()
        return [Percept.from_dict(json.loads(r["data"])) for r in rows]

    def high_salience(self, threshold: float, *, limit: int = 100) -> list[Percept]:
        rows = self._conn.execute(
            "SELECT data FROM percept WHERE salience >= ? ORDER BY salience DESC, rowid DESC LIMIT ?",
            (threshold, limit)).fetchall()
        return [Percept.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, kind: Optional[str] = None) -> int:
        if kind:
            return self._conn.execute("SELECT COUNT(*) c FROM percept WHERE kind=?", (kind,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM percept").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["PerceptionRepository"]
