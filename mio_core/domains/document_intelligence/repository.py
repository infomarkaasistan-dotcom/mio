"""MIO Core · Document Intelligence — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Document

_SCHEMA = """
CREATE TABLE IF NOT EXISTS document (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, doc_type TEXT NOT NULL, source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_doc_type ON document(doc_type);
"""


class DocumentRepository:
    def __init__(self, path: str = "mio_documents.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, doc: Document) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO document (id, title, doc_type, source, created_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET title=excluded.title, "
                "doc_type=excluded.doc_type, source=excluded.source, data=excluded.data",
                (doc.id, doc.title, doc.doc_type, doc.source, doc.created_at,
                 json.dumps(doc.to_dict(include_content=True), ensure_ascii=False)))
            self._conn.commit()

    def get(self, doc_id: str) -> Optional[Document]:
        r = self._conn.execute("SELECT data FROM document WHERE id=?", (doc_id,)).fetchone()
        return Document.from_dict(json.loads(r["data"])) if r else None

    def list(self, *, doc_type: Optional[str] = None) -> list[Document]:
        if doc_type:
            rows = self._conn.execute("SELECT data FROM document WHERE doc_type=? ORDER BY rowid",
                                      (doc_type,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM document ORDER BY rowid").fetchall()
        return [Document.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, *, doc_type: Optional[str] = None) -> int:
        if doc_type:
            return self._conn.execute("SELECT COUNT(*) c FROM document WHERE doc_type=?",
                                      (doc_type,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM document").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["DocumentRepository"]
