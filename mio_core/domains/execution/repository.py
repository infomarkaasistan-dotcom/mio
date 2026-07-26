"""MIO Core · Execution Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

Yürütme koşularını (denetim izi) kalıcılaştırır — orchestrator'ın araç-audit'inden AYRI, workflow düzeyi."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import ExecutionRun

_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_run (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '',
    plan_id TEXT, status TEXT NOT NULL, started_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_run_kind ON execution_run(kind);
CREATE INDEX IF NOT EXISTS ix_run_plan ON execution_run(plan_id);
"""


class ExecutionRepository:
    def __init__(self, path: str = "mio_execution.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, run: ExecutionRun) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO execution_run (id, kind, actor, plan_id, status, started_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
                "data=excluded.data",
                (run.id, run.kind, run.actor, run.plan_id, run.status, run.started_at,
                 json.dumps(run.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, run_id: str) -> Optional[ExecutionRun]:
        r = self._conn.execute("SELECT data FROM execution_run WHERE id=?", (run_id,)).fetchone()
        return ExecutionRun.from_dict(json.loads(r["data"])) if r else None

    def recent(self, limit: int = 100, *, kind: Optional[str] = None) -> list[ExecutionRun]:
        if kind:
            rows = self._conn.execute("SELECT data FROM execution_run WHERE kind=? "
                                      "ORDER BY rowid DESC LIMIT ?", (kind, limit)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM execution_run ORDER BY rowid DESC LIMIT ?",
                                      (limit,)).fetchall()
        return [ExecutionRun.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM execution_run WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM execution_run").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["ExecutionRepository"]
