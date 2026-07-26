"""MIO Core · Security Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

Principal'ları (RBAC) ve APPEND-ONLY güvenlik denetim izini tutar."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Principal, SecurityAudit

_SCHEMA = """
CREATE TABLE IF NOT EXISTS principal (
    name TEXT PRIMARY KEY, locked INTEGER NOT NULL DEFAULT 0, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS security_audit (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, principal TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'info', at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_audit_principal ON security_audit(principal);
CREATE INDEX IF NOT EXISTS ix_audit_kind ON security_audit(kind);
"""


class SecurityRepository:
    def __init__(self, path: str = "mio_security.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- principals ------------------------------------------------------- #
    def put_principal(self, p: Principal) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO principal (name, locked, data) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET locked=excluded.locked, data=excluded.data",
                (p.name, 1 if p.locked else 0, json.dumps(p.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_principal(self, name: str) -> Optional[Principal]:
        r = self._conn.execute("SELECT data FROM principal WHERE name=?", (name,)).fetchone()
        return Principal.from_dict(json.loads(r["data"])) if r else None

    def all_principals(self) -> list[Principal]:
        rows = self._conn.execute("SELECT data FROM principal ORDER BY name").fetchall()
        return [Principal.from_dict(json.loads(r["data"])) for r in rows]

    def principal_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM principal").fetchone()["c"]

    # -- audit (append-only) --------------------------------------------- #
    def append_audit(self, a: SecurityAudit) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO security_audit (id, kind, principal, severity, at, data) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (a.id, a.kind, a.principal, a.severity, a.at,
                 json.dumps(a.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def audit_recent(self, limit: int = 200, *, principal: Optional[str] = None) -> list[dict]:
        if principal:
            rows = self._conn.execute("SELECT data FROM security_audit WHERE principal=? "
                                      "ORDER BY rowid DESC LIMIT ?", (principal, limit)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM security_audit ORDER BY rowid DESC LIMIT ?",
                                      (limit,)).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def audit_count(self, *, severity: Optional[str] = None) -> int:
        if severity:
            return self._conn.execute("SELECT COUNT(*) c FROM security_audit WHERE severity=?",
                                      (severity,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM security_audit").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["SecurityRepository"]
