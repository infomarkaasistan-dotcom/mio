"""MIO Core · Marketplace Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Listing

_SCHEMA = """
CREATE TABLE IF NOT EXISTS listing (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_listing_kind_status ON listing(kind, status);
"""


class MarketplaceRepository:
    def __init__(self, path: str = "mio_marketplace.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, m: Listing) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO listing (id, name, kind, status, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
                "status=excluded.status, data=excluded.data",
                (m.id, m.name, m.kind, m.status, json.dumps(m.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, listing_id: str) -> Optional[Listing]:
        r = self._conn.execute("SELECT data FROM listing WHERE id=?", (listing_id,)).fetchone()
        return Listing.from_dict(json.loads(r["data"])) if r else None

    def all(self, *, kind: Optional[str] = None, status: Optional[str] = None) -> list[Listing]:
        clauses, params = [], []
        if kind:
            clauses.append("kind=?"); params.append(kind)
        if status:
            clauses.append("status=?"); params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(f"SELECT data FROM listing{where} ORDER BY rowid", params).fetchall()
        return [Listing.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM listing WHERE status=?", (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM listing").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["MarketplaceRepository"]
