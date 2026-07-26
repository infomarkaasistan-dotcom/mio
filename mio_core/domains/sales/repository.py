"""MIO Core · Sales & CRM — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Contact, Opportunity

_SCHEMA = """
CREATE TABLE IF NOT EXISTS contact (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS opportunity (
    id TEXT PRIMARY KEY, contact_id TEXT NOT NULL, stage TEXT NOT NULL, value REAL NOT NULL DEFAULT 0,
    data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_opp_stage ON opportunity(stage);
CREATE INDEX IF NOT EXISTS ix_opp_contact ON opportunity(contact_id);
"""


class SalesRepository:
    def __init__(self, path: str = "mio_sales.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- contacts -------------------------------------------------------- #
    def put_contact(self, c: Contact) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO contact (id, name, kind, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, kind=excluded.kind, data=excluded.data",
                (c.id, c.name, c.kind, json.dumps(c.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_contact(self, contact_id: str) -> Optional[Contact]:
        r = self._conn.execute("SELECT data FROM contact WHERE id=?", (contact_id,)).fetchone()
        return Contact.from_dict(json.loads(r["data"])) if r else None

    def all_contacts(self, *, kind: Optional[str] = None) -> list[Contact]:
        if kind:
            rows = self._conn.execute("SELECT data FROM contact WHERE kind=? ORDER BY rowid",
                                      (kind,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM contact ORDER BY rowid").fetchall()
        return [Contact.from_dict(json.loads(r["data"])) for r in rows]

    def contact_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM contact").fetchone()["c"]

    # -- opportunities --------------------------------------------------- #
    def put_opportunity(self, o: Opportunity) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO opportunity (id, contact_id, stage, value, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET stage=excluded.stage, value=excluded.value, data=excluded.data",
                (o.id, o.contact_id, o.stage, o.value, json.dumps(o.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_opportunity(self, opp_id: str) -> Optional[Opportunity]:
        r = self._conn.execute("SELECT data FROM opportunity WHERE id=?", (opp_id,)).fetchone()
        return Opportunity.from_dict(json.loads(r["data"])) if r else None

    def all_opportunities(self, *, stage: Optional[str] = None) -> list[Opportunity]:
        if stage:
            rows = self._conn.execute("SELECT data FROM opportunity WHERE stage=? ORDER BY rowid",
                                      (stage,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM opportunity ORDER BY rowid").fetchall()
        return [Opportunity.from_dict(json.loads(r["data"])) for r in rows]

    def opportunity_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM opportunity").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["SalesRepository"]
