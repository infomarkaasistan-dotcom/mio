"""MIO Core · Learning Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import LearningEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_event (
    id TEXT PRIMARY KEY, action TEXT NOT NULL, success INTEGER NOT NULL,
    created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_learn_action ON learning_event(action);
CREATE INDEX IF NOT EXISTS ix_learn_success ON learning_event(success);
"""


class LearningRepository:
    def __init__(self, path: str = "mio_learning.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, ev: LearningEvent) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO learning_event (id, action, success, created_at, data) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET action=excluded.action, "
                "success=excluded.success, data=excluded.data",
                (ev.id, ev.action, 1 if ev.success else 0, ev.created_at,
                 json.dumps(ev.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, ev_id: str) -> Optional[LearningEvent]:
        r = self._conn.execute("SELECT data FROM learning_event WHERE id=?", (ev_id,)).fetchone()
        return LearningEvent.from_dict(json.loads(r["data"])) if r else None

    def all(self) -> list[LearningEvent]:
        rows = self._conn.execute("SELECT data FROM learning_event ORDER BY rowid").fetchall()
        return [LearningEvent.from_dict(json.loads(r["data"])) for r in rows]

    def recent(self, limit: int = 100, *, with_lesson: bool = False) -> list[LearningEvent]:
        rows = self._conn.execute("SELECT data FROM learning_event ORDER BY rowid DESC LIMIT ?",
                                  (limit,)).fetchall()
        out = [LearningEvent.from_dict(json.loads(r["data"])) for r in rows]
        return [e for e in out if e.lesson] if with_lesson else out

    def success_counts(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT action, COUNT(*) c FROM learning_event WHERE success=1 GROUP BY action").fetchall()
        return {r["action"]: r["c"] for r in rows}

    def count(self, *, success: Optional[bool] = None) -> int:
        if success is None:
            return self._conn.execute("SELECT COUNT(*) c FROM learning_event").fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM learning_event WHERE success=?",
                                  (1 if success else 0,)).fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["LearningRepository"]
