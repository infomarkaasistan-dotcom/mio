"""MIO Core · Resource & Runtime — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

Bütçeleri (kalıcı) ve kaynak snapshot geçmişini tutar."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional
from uuid import uuid4

from .models import Budget

_SCHEMA = """
CREATE TABLE IF NOT EXISTS budget (
    name TEXT PRIMARY KEY, limit_val REAL NOT NULL, consumed REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'units', updated_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS resource_snapshot (
    id TEXT PRIMARY KEY, at TEXT NOT NULL, data TEXT NOT NULL);
"""


class ResourceRepository:
    def __init__(self, path: str = "mio_resources.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- budgets --------------------------------------------------------- #
    def put_budget(self, b: Budget) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO budget (name, limit_val, consumed, unit, updated_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET limit_val=excluded.limit_val, "
                "consumed=excluded.consumed, unit=excluded.unit, updated_at=excluded.updated_at, "
                "data=excluded.data",
                (b.name, b.limit, b.consumed, b.unit, b.updated_at,
                 json.dumps(b.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_budget(self, name: str) -> Optional[Budget]:
        r = self._conn.execute("SELECT data FROM budget WHERE name=?", (name,)).fetchone()
        return Budget.from_dict(json.loads(r["data"])) if r else None

    def all_budgets(self) -> list[Budget]:
        rows = self._conn.execute("SELECT data FROM budget ORDER BY name").fetchall()
        return [Budget.from_dict(json.loads(r["data"])) for r in rows]

    def budget_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM budget").fetchone()["c"]

    # -- snapshots ------------------------------------------------------- #
    def append_snapshot(self, snapshot: dict, at: str) -> None:
        with self._lock:
            self._conn.execute("INSERT INTO resource_snapshot (id, at, data) VALUES (?, ?, ?)",
                               (uuid4().hex[:16], at, json.dumps(snapshot, ensure_ascii=False)))
            self._conn.commit()

    def latest_snapshot(self) -> Optional[dict]:
        r = self._conn.execute("SELECT data FROM resource_snapshot ORDER BY rowid DESC LIMIT 1").fetchone()
        return json.loads(r["data"]) if r else None

    def prune_snapshots(self, keep: int) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM resource_snapshot WHERE id NOT IN "
                "(SELECT id FROM resource_snapshot ORDER BY rowid DESC LIMIT ?)", (keep,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["ResourceRepository"]
