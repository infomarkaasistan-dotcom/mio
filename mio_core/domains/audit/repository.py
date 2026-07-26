"""MIO Core · Audit & Compliance — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

audit_ledger APPEND-ONLY (değişmez); compliance_record kapsam+madde başına upsert (güncel uyum durumu)."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import AuditRecord, ComplianceRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_ledger (
    id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, resource TEXT NOT NULL DEFAULT '',
    outcome TEXT NOT NULL DEFAULT 'success', severity TEXT NOT NULL DEFAULT 'info', at TEXT NOT NULL,
    data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_audit_action ON audit_ledger(action);
CREATE INDEX IF NOT EXISTS ix_audit_actor ON audit_ledger(actor);
CREATE INDEX IF NOT EXISTS ix_audit_outcome ON audit_ledger(outcome);
CREATE TABLE IF NOT EXISTS compliance_record (
    key TEXT PRIMARY KEY, scope TEXT NOT NULL, article TEXT NOT NULL, level TEXT NOT NULL,
    updated_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_comp_scope ON compliance_record(scope);
"""


class AuditRepository:
    def __init__(self, path: str = "mio_audit.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- audit ledger (append-only) -------------------------------------- #
    def append_audit(self, rec: AuditRecord) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO audit_ledger (id, actor, action, resource, outcome, severity, at, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rec.id, rec.actor, rec.action, rec.resource, rec.outcome, rec.severity, rec.at,
                 json.dumps(rec.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def audit_recent(self, limit: int = 500, *, actor: Optional[str] = None, action: Optional[str] = None,
                     outcome: Optional[str] = None) -> list[dict]:
        conds, args = [], []
        if actor:
            conds.append("actor=?"); args.append(actor)
        if action:
            conds.append("action=?"); args.append(action)
        if outcome:
            conds.append("outcome=?"); args.append(outcome)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        args.append(limit)
        rows = self._conn.execute(
            f"SELECT data FROM audit_ledger{where} ORDER BY rowid DESC LIMIT ?", args).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def audit_count(self, *, outcome: Optional[str] = None) -> int:
        if outcome:
            return self._conn.execute("SELECT COUNT(*) c FROM audit_ledger WHERE outcome=?",
                                      (outcome,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM audit_ledger").fetchone()["c"]

    # -- compliance records (upsert) ------------------------------------- #
    def put_compliance(self, rec: ComplianceRecord) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO compliance_record (key, scope, article, level, updated_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET scope=excluded.scope, "
                "article=excluded.article, level=excluded.level, updated_at=excluded.updated_at, "
                "data=excluded.data",
                (rec.key(), rec.scope, rec.article, rec.level, rec.updated_at,
                 json.dumps(rec.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def all_compliance(self) -> list[dict]:
        rows = self._conn.execute("SELECT data FROM compliance_record ORDER BY scope, article").fetchall()
        return [json.loads(r["data"]) for r in rows]

    def compliance_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM compliance_record").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["AuditRepository"]
