"""MIO Core · Finance Operations — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Commitment, Transaction

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transaction_entry (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL,
    category TEXT NOT NULL, at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_txn_kind ON transaction_entry(kind);
CREATE INDEX IF NOT EXISTS ix_txn_cat ON transaction_entry(category);
CREATE TABLE IF NOT EXISTS commitment (
    id TEXT PRIMARY KEY, status TEXT NOT NULL, amount REAL NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_commit_status ON commitment(status);
"""


class FinanceRepository:
    def __init__(self, path: str = "mio_finance.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- transactions ---------------------------------------------------- #
    def add_transaction(self, t: Transaction) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO transaction_entry (id, kind, amount, currency, category, at, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (t.id, t.kind, t.amount, t.currency, t.category, t.at,
                 json.dumps(t.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def all_transactions(self, *, kind: Optional[str] = None) -> list[Transaction]:
        if kind:
            rows = self._conn.execute("SELECT data FROM transaction_entry WHERE kind=? ORDER BY rowid",
                                      (kind,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM transaction_entry ORDER BY rowid").fetchall()
        return [Transaction.from_dict(json.loads(r["data"])) for r in rows]

    def sum_by_kind(self, kind: str) -> float:
        r = self._conn.execute("SELECT COALESCE(SUM(amount),0) s FROM transaction_entry WHERE kind=?",
                               (kind,)).fetchone()
        return float(r["s"])

    def transaction_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM transaction_entry").fetchone()["c"]

    # -- commitments ----------------------------------------------------- #
    def put_commitment(self, c: Commitment) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO commitment (id, status, amount, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (c.id, c.status, c.amount, json.dumps(c.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_commitment(self, commitment_id: str) -> Optional[Commitment]:
        r = self._conn.execute("SELECT data FROM commitment WHERE id=?", (commitment_id,)).fetchone()
        return Commitment.from_dict(json.loads(r["data"])) if r else None

    def list_commitments(self, *, status: Optional[str] = None) -> list[Commitment]:
        if status:
            rows = self._conn.execute("SELECT data FROM commitment WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM commitment ORDER BY rowid").fetchall()
        return [Commitment.from_dict(json.loads(r["data"])) for r in rows]

    def commitment_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM commitment WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM commitment").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["FinanceRepository"]
