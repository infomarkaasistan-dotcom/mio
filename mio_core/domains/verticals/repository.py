"""MIO Core · Vertical Domain Brains — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

Tüm dikey beyinlerin ürettiği tavsiyeleri (advice) tek tabloda tutar; brain sütunuyla ayrışır."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Advice

_SCHEMA = """
CREATE TABLE IF NOT EXISTS advice (
    id TEXT PRIMARY KEY, brain TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 0.0,
    at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_advice_brain ON advice(brain);
"""


class AdviceRepository:
    def __init__(self, path: str = "mio_verticals.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, advice: Advice) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO advice (id, brain, confidence, at, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET brain=excluded.brain, confidence=excluded.confidence, "
                "data=excluded.data",
                (advice.id, advice.brain, advice.confidence, advice.at,
                 json.dumps(advice.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, advice_id: str) -> Optional[Advice]:
        r = self._conn.execute("SELECT data FROM advice WHERE id=?", (advice_id,)).fetchone()
        return Advice.from_dict(json.loads(r["data"])) if r else None

    def recent(self, brain: str, limit: int = 100) -> list[Advice]:
        rows = self._conn.execute("SELECT data FROM advice WHERE brain=? ORDER BY rowid DESC LIMIT ?",
                                  (brain, limit)).fetchall()
        return [Advice.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, brain: Optional[str] = None) -> int:
        if brain:
            return self._conn.execute("SELECT COUNT(*) c FROM advice WHERE brain=?", (brain,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM advice").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["AdviceRepository"]
