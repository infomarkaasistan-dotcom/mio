"""MIO Core · Capability Management — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

İki sorumluluk: (a) maturity/state override'ları (yeniden başlatmada in-memory registry'ye geri uygulanır),
(b) append-only capability lifecycle denetimi (Capability Evolution — Madde 26)."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional
from uuid import uuid4

_SCHEMA = """
CREATE TABLE IF NOT EXISTS capability_state (
    name TEXT PRIMARY KEY, maturity TEXT NOT NULL, contract_version TEXT NOT NULL DEFAULT '1.0.0',
    updated_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS capability_lifecycle (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
    at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_caplc_name ON capability_lifecycle(name);
"""


class CapabilityRepository:
    def __init__(self, path: str = "mio_capabilities.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put_state(self, name: str, maturity: str, contract_version: str, updated_at: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO capability_state (name, maturity, contract_version, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET maturity=excluded.maturity, "
                "contract_version=excluded.contract_version, updated_at=excluded.updated_at",
                (name, maturity, contract_version, updated_at))
            self._conn.commit()

    def all_states(self) -> list[tuple[str, str, str]]:
        rows = self._conn.execute(
            "SELECT name, maturity, contract_version FROM capability_state").fetchall()
        return [(r["name"], r["maturity"], r["contract_version"]) for r in rows]

    def append_lifecycle(self, name: str, kind: str, detail: str, at: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO capability_lifecycle (id, name, kind, detail, at) VALUES (?, ?, ?, ?, ?)",
                (uuid4().hex[:16], name, kind, detail, at))
            self._conn.commit()

    def lifecycle_recent(self, limit: int = 100, *, name: Optional[str] = None) -> list[dict]:
        if name:
            rows = self._conn.execute("SELECT name, kind, detail, at FROM capability_lifecycle "
                                      "WHERE name=? ORDER BY rowid DESC LIMIT ?", (name, limit)).fetchall()
        else:
            rows = self._conn.execute("SELECT name, kind, detail, at FROM capability_lifecycle "
                                      "ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def lifecycle_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM capability_lifecycle").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["CapabilityRepository"]
