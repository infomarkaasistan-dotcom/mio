"""MIO Core · Communication Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Conversation

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation (
    id TEXT PRIMARY KEY, turns INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_conv_updated ON conversation(updated_at);
"""


class ConversationRepository:
    def __init__(self, path: str = "mio_conversations.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, conv: Conversation) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO conversation (id, turns, updated_at, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET turns=excluded.turns, updated_at=excluded.updated_at, "
                "data=excluded.data",
                (conv.id, len(conv.turns), conv.updated_at,
                 json.dumps(conv.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, conv_id: str) -> Optional[Conversation]:
        r = self._conn.execute("SELECT data FROM conversation WHERE id=?", (conv_id,)).fetchone()
        return Conversation.from_dict(json.loads(r["data"])) if r else None

    def recent(self, limit: int = 50) -> list[Conversation]:
        rows = self._conn.execute("SELECT data FROM conversation ORDER BY updated_at DESC LIMIT ?",
                                  (limit,)).fetchall()
        return [Conversation.from_dict(json.loads(r["data"])) for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM conversation").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["ConversationRepository"]
