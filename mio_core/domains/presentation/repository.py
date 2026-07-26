"""MIO Core · Presentation Domain — Repository (SQLite, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Script, Session

_SCHEMA = """
CREATE TABLE IF NOT EXISTS script (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY, script_id TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_script_kind ON script(kind);
CREATE INDEX IF NOT EXISTS ix_session_status ON session(status);
"""


class PresentationRepository:
    def __init__(self, path: str = "mio_presentation.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- scripts --------------------------------------------------------- #
    def put_script(self, s: Script) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO script (id, title, kind, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, kind=excluded.kind, data=excluded.data",
                (s.id, s.title, s.kind, json.dumps(s.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_script(self, script_id: str) -> Optional[Script]:
        r = self._conn.execute("SELECT data FROM script WHERE id=?", (script_id,)).fetchone()
        return Script.from_dict(json.loads(r["data"])) if r else None

    def all_scripts(self, *, kind: Optional[str] = None) -> list[Script]:
        if kind:
            rows = self._conn.execute("SELECT data FROM script WHERE kind=? ORDER BY rowid", (kind,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM script ORDER BY rowid").fetchall()
        return [Script.from_dict(json.loads(r["data"])) for r in rows]

    def script_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM script").fetchone()["c"]

    # -- sessions -------------------------------------------------------- #
    def put_session(self, s: Session) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO session (id, script_id, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (s.id, s.script_id, s.status, json.dumps(s.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_session(self, session_id: str) -> Optional[Session]:
        r = self._conn.execute("SELECT data FROM session WHERE id=?", (session_id,)).fetchone()
        return Session.from_dict(json.loads(r["data"])) if r else None

    def all_sessions(self, *, status: Optional[str] = None) -> list[Session]:
        if status:
            rows = self._conn.execute("SELECT data FROM session WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM session ORDER BY rowid").fetchall()
        return [Session.from_dict(json.loads(r["data"])) for r in rows]

    def session_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM session WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM session").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["PresentationRepository"]
