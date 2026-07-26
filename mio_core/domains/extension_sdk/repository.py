"""MIO Core · Extension SDK Domain — Repository (SQLite, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Extension

_SCHEMA = """
CREATE TABLE IF NOT EXISTS extension (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ext_kind_status ON extension(kind, status);
"""


class ExtensionRepository:
    def __init__(self, path: str = "mio_extensions.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, e: Extension) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO extension (id, name, kind, status, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
                "status=excluded.status, data=excluded.data",
                (e.id, e.name, e.kind, e.status, json.dumps(e.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, ext_id: str) -> Optional[Extension]:
        r = self._conn.execute("SELECT data FROM extension WHERE id=?", (ext_id,)).fetchone()
        return Extension.from_dict(json.loads(r["data"])) if r else None

    def all(self, *, kind: Optional[str] = None, status: Optional[str] = None) -> list[Extension]:
        clauses, params = [], []
        if kind:
            clauses.append("kind=?"); params.append(kind)
        if status:
            clauses.append("status=?"); params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(f"SELECT data FROM extension{where} ORDER BY rowid", params).fetchall()
        return [Extension.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM extension WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM extension").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["ExtensionRepository"]
