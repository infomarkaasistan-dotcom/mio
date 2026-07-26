"""MIO Core · Knowledge Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

YALNIZCA yaşayan (learned) bilgiyi kalıcılaştırır — innate bilgi doğuşta tohumlanır, saklanmaz.
Öğren/pekiştir/unut anında write-through: çöküşe dayanıklı (WAL), close beklemez."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from mio_core.knowledge import KnowledgeItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge (
    id TEXT PRIMARY KEY, ktype TEXT NOT NULL, name TEXT NOT NULL, domain TEXT NOT NULL DEFAULT 'general',
    source TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 0.7, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_know_ktype ON knowledge(ktype);
CREATE INDEX IF NOT EXISTS ix_know_domain ON knowledge(domain);
"""


class KnowledgeRepository:
    def __init__(self, path: str = "mio_knowledge.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, item: KnowledgeItem) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO knowledge (id, ktype, name, domain, source, confidence, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET ktype=excluded.ktype, "
                "name=excluded.name, domain=excluded.domain, source=excluded.source, "
                "confidence=excluded.confidence, data=excluded.data",
                (item.id, item.ktype.value, item.name, item.domain, item.source, item.confidence,
                 json.dumps(item.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, item_id: str) -> Optional[KnowledgeItem]:
        r = self._conn.execute("SELECT data FROM knowledge WHERE id=?", (item_id,)).fetchone()
        return KnowledgeItem.from_dict(json.loads(r["data"])) if r else None

    def delete(self, item_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM knowledge WHERE id=?", (item_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def all(self) -> list[KnowledgeItem]:
        rows = self._conn.execute("SELECT data FROM knowledge ORDER BY rowid").fetchall()
        return [KnowledgeItem.from_dict(json.loads(r["data"])) for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM knowledge").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["KnowledgeRepository"]
