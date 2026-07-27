"""MIO Core · Platform · Session Store — kalıcı, cihazlar-arası SENKRON konuşma oturumları, stdlib-only.

Conversation Runtime'ın kalıcılık tabanı. Her oturum bir `session_id` + sıralı mesaj akışıdır. Kalıcı olduğu için
**herhangi bir istemci (masaüstü/telefon/web/ses) aynı session_id ile bağlanıp kesintisiz devam eder** — masaüstünde
başlanan sohbet telefonda görünür (senkron). Yeni registry/mimari DEĞİL; Business Workspace gibi bir platform
servisi. SQLite (WAL + threading.Lock) — mevcut repository deseniyle aynı. İş mantığı YOK (yalnız saklama)."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

_SCHEMA = """
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, actor TEXT NOT NULL,
    business_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS session_message (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, seq INTEGER NOT NULL,
    role TEXT NOT NULL, text TEXT NOT NULL, intent TEXT, data TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_msg_session ON session_message(session_id, seq);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    """Konuşma oturumlarını + sıralı mesajlarını kalıcı saklar (SQLite WAL). Cihazlar arası senkron zemin."""

    def __init__(self, path: str = "mio_sessions.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- oturum ---------------------------------------------------------- #
    def create_session(self, *, title: str = "", actor: str = "owner",
                        business_id: Optional[str] = None, session_id: Optional[str] = None) -> dict[str, Any]:
        sid = session_id or uuid4().hex[:12]
        now = _now()
        title = (title or "").strip() or f"Sohbet {now[:16].replace('T', ' ')}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO session (id, title, actor, business_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
                (sid, title, actor, business_id, now, now))
            self._conn.commit()
        return self.get_session(sid)  # type: ignore[return-value]

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        r = self._conn.execute("SELECT * FROM session WHERE id=?", (session_id,)).fetchone()
        if r is None:
            return None
        out = dict(r)
        out["messages"] = self.message_count(session_id)
        return out

    def list_sessions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM session ORDER BY updated_at DESC LIMIT ?", (int(limit),)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["messages"] = self.message_count(d["id"])
            out.append(d)
        return out

    def delete_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.execute("DELETE FROM session WHERE id=?", (session_id,))
            self._conn.execute("DELETE FROM session_message WHERE session_id=?", (session_id,))
            self._conn.commit()
        return {"deleted": session_id, "existed": cur.rowcount > 0}

    # -- mesaj ----------------------------------------------------------- #
    def append_message(self, session_id: str, role: str, text: str, *, intent: Optional[str] = None,
                       data: Optional[Any] = None) -> dict[str, Any]:
        now = _now()
        mid = uuid4().hex[:12]
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM session_message WHERE session_id=?",
                (session_id,)).fetchone()
            seq = row["n"]
            self._conn.execute(
                "INSERT INTO session_message (id, session_id, seq, role, text, intent, data, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (mid, session_id, seq, role, text, intent,
                 json.dumps(data, ensure_ascii=False) if data is not None else None, now))
            self._conn.execute("UPDATE session SET updated_at=? WHERE id=?", (now, session_id))
            self._conn.commit()
        return {"id": mid, "session_id": session_id, "seq": seq, "role": role, "text": text,
                "intent": intent, "created_at": now}

    def get_messages(self, session_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM session_message WHERE session_id=? ORDER BY seq LIMIT ?",
            (session_id, int(limit))).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["data"] = json.loads(d["data"]) if d["data"] else None
            out.append(d)
        return out

    def message_count(self, session_id: str) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) c FROM session_message WHERE session_id=?", (session_id,)).fetchone()["c"]

    def stats(self) -> dict[str, Any]:
        s = self._conn.execute("SELECT COUNT(*) c FROM session").fetchone()["c"]
        m = self._conn.execute("SELECT COUNT(*) c FROM session_message").fetchone()["c"]
        return {"sessions": s, "messages": m}

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["SessionStore"]
