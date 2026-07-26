"""MIO Core · Reasoning Domain — Repository (SQLite, kalıcı), stdlib-only, LLM-BAĞIMSIZ.

Muhakeme izlerini (trace) kalıcılaştırır: açıklanabilirlik + denetim (E1 audit ruhu). Write-through, WAL."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import ReasoningTrace

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reasoning_trace (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.0, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_trace_kind ON reasoning_trace(kind);
"""


class ReasoningRepository:
    def __init__(self, path: str = "mio_reasoning.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, trace: ReasoningTrace) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO reasoning_trace (id, kind, actor, confidence, created_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, "
                "actor=excluded.actor, confidence=excluded.confidence, data=excluded.data",
                (trace.id, trace.kind, trace.actor, trace.confidence, trace.created_at,
                 json.dumps(trace.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, trace_id: str) -> Optional[ReasoningTrace]:
        r = self._conn.execute("SELECT data FROM reasoning_trace WHERE id=?", (trace_id,)).fetchone()
        return ReasoningTrace.from_dict(json.loads(r["data"])) if r else None

    def recent(self, limit: int = 50, *, kind: Optional[str] = None) -> list[ReasoningTrace]:
        if kind:
            rows = self._conn.execute("SELECT data FROM reasoning_trace WHERE kind=? "
                                      "ORDER BY rowid DESC LIMIT ?", (kind, limit)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM reasoning_trace ORDER BY rowid DESC LIMIT ?",
                                      (limit,)).fetchall()
        return [ReasoningTrace.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, kind: Optional[str] = None) -> int:
        if kind:
            return self._conn.execute("SELECT COUNT(*) c FROM reasoning_trace WHERE kind=?",
                                      (kind,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM reasoning_trace").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["ReasoningRepository"]
