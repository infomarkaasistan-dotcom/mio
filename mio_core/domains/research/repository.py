"""MIO Core · Research Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Finding, Inquiry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS inquiry (
    id TEXT PRIMARY KEY, question TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS finding (
    id TEXT PRIMARY KEY, inquiry_id TEXT NOT NULL, source TEXT NOT NULL DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_finding_inquiry ON finding(inquiry_id);
"""


class ResearchRepository:
    def __init__(self, path: str = "mio_research.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put_inquiry(self, q: Inquiry) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO inquiry (id, question, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET question=excluded.question, status=excluded.status, "
                "data=excluded.data",
                (q.id, q.question, q.status, json.dumps(q.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_inquiry(self, inquiry_id: str) -> Optional[Inquiry]:
        r = self._conn.execute("SELECT data FROM inquiry WHERE id=?", (inquiry_id,)).fetchone()
        return Inquiry.from_dict(json.loads(r["data"])) if r else None

    def all_inquiries(self, *, status: Optional[str] = None) -> list[Inquiry]:
        if status:
            rows = self._conn.execute("SELECT data FROM inquiry WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM inquiry ORDER BY rowid").fetchall()
        return [Inquiry.from_dict(json.loads(r["data"])) for r in rows]

    def inquiry_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM inquiry").fetchone()["c"]

    def put_finding(self, f: Finding) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO finding (id, inquiry_id, source, verified, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET source=excluded.source, verified=excluded.verified, "
                "data=excluded.data",
                (f.id, f.inquiry_id, f.source, 1 if f.verified else 0,
                 json.dumps(f.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_finding(self, finding_id: str) -> Optional[Finding]:
        r = self._conn.execute("SELECT data FROM finding WHERE id=?", (finding_id,)).fetchone()
        return Finding.from_dict(json.loads(r["data"])) if r else None

    def findings_for(self, inquiry_id: str) -> list[Finding]:
        rows = self._conn.execute("SELECT data FROM finding WHERE inquiry_id=? ORDER BY rowid",
                                  (inquiry_id,)).fetchall()
        return [Finding.from_dict(json.loads(r["data"])) for r in rows]

    def finding_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM finding").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["ResearchRepository"]
