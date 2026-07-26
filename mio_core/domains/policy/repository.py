"""MIO Core · Policy Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Policy

_SCHEMA = """
CREATE TABLE IF NOT EXISTS policy (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, effect TEXT NOT NULL, scope TEXT NOT NULL DEFAULT '*',
    priority INTEGER NOT NULL DEFAULT 50, enabled INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL,
    data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_policy_scope ON policy(scope);
"""


class PolicyRepository:
    def __init__(self, path: str = "mio_policy.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, p: Policy) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO policy (id, name, effect, scope, priority, enabled, source, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, "
                "effect=excluded.effect, scope=excluded.scope, priority=excluded.priority, "
                "enabled=excluded.enabled, source=excluded.source, data=excluded.data",
                (p.id, p.name, p.effect, p.scope, p.priority, 1 if p.enabled else 0, p.source,
                 json.dumps(p.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, policy_id: str) -> Optional[Policy]:
        r = self._conn.execute("SELECT data FROM policy WHERE id=?", (policy_id,)).fetchone()
        return Policy.from_dict(json.loads(r["data"])) if r else None

    def get_by_name(self, name: str) -> Optional[Policy]:
        r = self._conn.execute("SELECT data FROM policy WHERE name=?", (name,)).fetchone()
        return Policy.from_dict(json.loads(r["data"])) if r else None

    def all(self) -> list[Policy]:
        rows = self._conn.execute("SELECT data FROM policy ORDER BY priority DESC, rowid").fetchall()
        return [Policy.from_dict(json.loads(r["data"])) for r in rows]

    def delete(self, policy_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM policy WHERE id=?", (policy_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM policy").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["PolicyRepository"]
