"""MIO Core · Observability Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

Metrikleri (sayaç/gauge; olay-tipi sayaçları dahil) ve telemetri olay halkasını kalıcılaştırır."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import TelemetryEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metric (
    name TEXT PRIMARY KEY, value REAL NOT NULL DEFAULT 0, kind TEXT NOT NULL DEFAULT 'counter',
    updated_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS telemetry_event (
    id TEXT PRIMARY KEY, type TEXT NOT NULL, at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_tel_type ON telemetry_event(type);
"""


class TelemetryRepository:
    def __init__(self, path: str = "mio_observability.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put_metric(self, name: str, value: float, kind: str, updated_at: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO metric (name, value, kind, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value=excluded.value, kind=excluded.kind, "
                "updated_at=excluded.updated_at",
                (name, value, kind, updated_at))
            self._conn.commit()

    def all_metrics(self) -> list[tuple[str, float, str]]:
        rows = self._conn.execute("SELECT name, value, kind FROM metric").fetchall()
        return [(r["name"], r["value"], r["kind"]) for r in rows]

    def append_event(self, ev: TelemetryEvent) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO telemetry_event (id, type, at, data) VALUES (?, ?, ?, ?)",
                (ev.id, ev.type, ev.at, json.dumps(ev.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def recent_events(self, limit: int = 100, *, type: Optional[str] = None) -> list[dict]:
        if type:
            rows = self._conn.execute("SELECT data FROM telemetry_event WHERE type=? "
                                      "ORDER BY rowid DESC LIMIT ?", (type, limit)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM telemetry_event ORDER BY rowid DESC LIMIT ?",
                                      (limit,)).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def event_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM telemetry_event").fetchone()["c"]

    def prune_events(self, keep: int) -> int:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM telemetry_event WHERE id NOT IN "
                "(SELECT id FROM telemetry_event ORDER BY rowid DESC LIMIT ?)", (keep,))
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["TelemetryRepository"]
