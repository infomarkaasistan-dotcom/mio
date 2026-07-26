"""MIO Core · Business & Operations — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import BusinessRule, Process

_SCHEMA = """
CREATE TABLE IF NOT EXISTS process (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS business_rule (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 50, data TEXT NOT NULL);
"""


class BusinessRepository:
    def __init__(self, path: str = "mio_business.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- processes ------------------------------------------------------- #
    def put_process(self, p: Process) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO process (id, name, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, status=excluded.status, data=excluded.data",
                (p.id, p.name, p.status, json.dumps(p.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_process(self, process_id: str) -> Optional[Process]:
        r = self._conn.execute("SELECT data FROM process WHERE id=?", (process_id,)).fetchone()
        return Process.from_dict(json.loads(r["data"])) if r else None

    def list_processes(self, *, status: Optional[str] = None) -> list[Process]:
        if status:
            rows = self._conn.execute("SELECT data FROM process WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM process ORDER BY rowid").fetchall()
        return [Process.from_dict(json.loads(r["data"])) for r in rows]

    def process_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM process").fetchone()["c"]

    # -- rules ----------------------------------------------------------- #
    def put_rule(self, r: BusinessRule) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO business_rule (id, name, priority, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, priority=excluded.priority, "
                "data=excluded.data",
                (r.id, r.name, r.priority, json.dumps(r.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_rule_by_name(self, name: str) -> Optional[BusinessRule]:
        r = self._conn.execute("SELECT data FROM business_rule WHERE name=?", (name,)).fetchone()
        return BusinessRule.from_dict(json.loads(r["data"])) if r else None

    def all_rules(self) -> list[BusinessRule]:
        rows = self._conn.execute("SELECT data FROM business_rule ORDER BY priority DESC, rowid").fetchall()
        return [BusinessRule.from_dict(json.loads(r["data"])) for r in rows]

    def rule_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM business_rule").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["BusinessRepository"]
