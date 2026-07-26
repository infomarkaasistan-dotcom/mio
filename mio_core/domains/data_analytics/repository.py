"""MIO Core · Data Analytics — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Dataset

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, row_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, data TEXT NOT NULL);
"""


class DataRepository:
    def __init__(self, path: str = "mio_data.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, ds: Dataset) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO dataset (id, name, row_count, created_at, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, row_count=excluded.row_count, "
                "data=excluded.data",
                (ds.id, ds.name, len(ds.rows), ds.created_at,
                 json.dumps(ds.to_dict(include_rows=True), ensure_ascii=False)))
            self._conn.commit()

    def get(self, dataset_id: str) -> Optional[Dataset]:
        r = self._conn.execute("SELECT data FROM dataset WHERE id=?", (dataset_id,)).fetchone()
        return Dataset.from_dict(json.loads(r["data"])) if r else None

    def list(self) -> list[Dataset]:
        rows = self._conn.execute("SELECT data FROM dataset ORDER BY rowid").fetchall()
        return [Dataset.from_dict(json.loads(r["data"])) for r in rows]

    def delete(self, dataset_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM dataset WHERE id=?", (dataset_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM dataset").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["DataRepository"]
