"""MIO Core · Workflow Domain — Repository (SQLite, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Workflow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_wf_status ON workflow(status);
"""


class WorkflowRepository:
    def __init__(self, path: str = "mio_workflow.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, w: Workflow) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO workflow (id, name, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, status=excluded.status, data=excluded.data",
                (w.id, w.name, w.status, json.dumps(w.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, workflow_id: str) -> Optional[Workflow]:
        r = self._conn.execute("SELECT data FROM workflow WHERE id=?", (workflow_id,)).fetchone()
        return Workflow.from_dict(json.loads(r["data"])) if r else None

    def all(self, *, status: Optional[str] = None) -> list[Workflow]:
        if status:
            rows = self._conn.execute("SELECT data FROM workflow WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM workflow ORDER BY rowid").fetchall()
        return [Workflow.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM workflow WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM workflow").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["WorkflowRepository"]
