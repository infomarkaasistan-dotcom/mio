"""MIO Core · Memory Domain — Repository katmanı (SQLite, kalıcı), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import MemoryItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    id TEXT PRIMARY KEY, mtype TEXT NOT NULL, strength REAL NOT NULL DEFAULT 1.0,
    content TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '', data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_mem_type ON memory(mtype);
"""


class MemoryRepository:
    def __init__(self, path: str = "mio_memory.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, item: MemoryItem) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO memory (id, mtype, strength, content, tags, data) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET mtype=excluded.mtype, strength=excluded.strength, "
                "content=excluded.content, tags=excluded.tags, data=excluded.data",
                (item.id, item.mtype, item.strength, item.content, " ".join(item.tags),
                 json.dumps(item.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, item_id: str) -> Optional[MemoryItem]:
        r = self._conn.execute("SELECT data FROM memory WHERE id=?", (item_id,)).fetchone()
        return MemoryItem.from_dict(json.loads(r["data"])) if r else None

    def list(self, mtype: Optional[str] = None) -> list[MemoryItem]:
        if mtype:
            rows = self._conn.execute("SELECT data FROM memory WHERE mtype=? ORDER BY rowid", (mtype,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM memory ORDER BY rowid").fetchall()
        return [MemoryItem.from_dict(json.loads(r["data"])) for r in rows]

    def delete(self, item_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM memory WHERE id=?", (item_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def search(self, keywords: list[str], *, mtype: Optional[str] = None, limit: int = 20) -> list[MemoryItem]:
        kws = [k.strip().lower() for k in keywords if k and k.strip()]
        if not kws:
            return []
        rows = (self._conn.execute("SELECT content, tags, strength, data FROM memory WHERE mtype=?", (mtype,))
                if mtype else self._conn.execute("SELECT content, tags, strength, data FROM memory")).fetchall()
        scored = []
        for r in rows:
            hay = (r["content"] + " " + (r["tags"] or "")).lower()
            score = sum(1 for k in kws if k in hay)
            if score:
                scored.append((score, r["strength"], MemoryItem.from_dict(json.loads(r["data"]))))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [it for _, _, it in scored[:limit]]

    def count(self, mtype: Optional[str] = None) -> int:
        if mtype:
            return self._conn.execute("SELECT COUNT(*) c FROM memory WHERE mtype=?", (mtype,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM memory").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["MemoryRepository"]
