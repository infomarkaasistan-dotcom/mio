"""MIO Core · Conversation Domain — Repository (SQLite, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Message, UserProfile

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conv_user (
    id TEXT PRIMARY KEY, handle TEXT NOT NULL UNIQUE, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conv_message (
    id TEXT PRIMARY KEY, user_handle TEXT NOT NULL, priority TEXT NOT NULL,
    answered INTEGER NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_msg_user ON conv_message(user_handle);
CREATE INDEX IF NOT EXISTS ix_msg_queue ON conv_message(answered, priority);
"""


class ConversationRepository:
    def __init__(self, path: str = "mio_conversation.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- users ----------------------------------------------------------- #
    def put_user(self, u: UserProfile) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO conv_user (id, handle, data) VALUES (?, ?, ?) "
                "ON CONFLICT(handle) DO UPDATE SET data=excluded.data",
                (u.id, u.handle, json.dumps({**u.to_dict(), "last_texts": u.last_texts}, ensure_ascii=False)))
            self._conn.commit()

    def get_user(self, handle: str) -> Optional[UserProfile]:
        r = self._conn.execute("SELECT data FROM conv_user WHERE handle=?", (handle,)).fetchone()
        return UserProfile.from_dict(json.loads(r["data"])) if r else None

    def all_users(self) -> list[UserProfile]:
        rows = self._conn.execute("SELECT data FROM conv_user ORDER BY rowid").fetchall()
        return [UserProfile.from_dict(json.loads(r["data"])) for r in rows]

    def user_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM conv_user").fetchone()["c"]

    # -- messages -------------------------------------------------------- #
    def put_message(self, m: Message) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO conv_message (id, user_handle, priority, answered, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET answered=excluded.answered, data=excluded.data",
                (m.id, m.user_handle, m.priority, 1 if m.answered else 0,
                 json.dumps(m.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_message(self, message_id: str) -> Optional[Message]:
        r = self._conn.execute("SELECT data FROM conv_message WHERE id=?", (message_id,)).fetchone()
        return Message.from_dict(json.loads(r["data"])) if r else None

    def all_messages(self, *, unanswered_only: bool = False) -> list[Message]:
        if unanswered_only:
            rows = self._conn.execute(
                "SELECT data FROM conv_message WHERE answered=0 ORDER BY rowid").fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM conv_message ORDER BY rowid").fetchall()
        return [Message.from_dict(json.loads(r["data"])) for r in rows]

    def message_count(self, *, unanswered_only: bool = False) -> int:
        if unanswered_only:
            return self._conn.execute("SELECT COUNT(*) c FROM conv_message WHERE answered=0").fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM conv_message").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["ConversationRepository"]
