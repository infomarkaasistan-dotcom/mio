"""MIO Core · Customer Success — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Account, Feedback, Ticket

_SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ticket (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, status TEXT NOT NULL, priority TEXT NOT NULL,
    data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ticket_acct ON ticket(account_id);
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, score INTEGER NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_fb_acct ON feedback(account_id);
"""


class CustomerRepository:
    def __init__(self, path: str = "mio_customer.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- accounts -------------------------------------------------------- #
    def put_account(self, a: Account) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO account (id, name, data) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, data=excluded.data",
                (a.id, a.name, json.dumps(a.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_account(self, account_id: str) -> Optional[Account]:
        r = self._conn.execute("SELECT data FROM account WHERE id=?", (account_id,)).fetchone()
        return Account.from_dict(json.loads(r["data"])) if r else None

    def all_accounts(self) -> list[Account]:
        rows = self._conn.execute("SELECT data FROM account ORDER BY rowid").fetchall()
        return [Account.from_dict(json.loads(r["data"])) for r in rows]

    def account_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM account").fetchone()["c"]

    # -- tickets --------------------------------------------------------- #
    def put_ticket(self, t: Ticket) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO ticket (id, account_id, status, priority, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (t.id, t.account_id, t.status, t.priority, json.dumps(t.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        r = self._conn.execute("SELECT data FROM ticket WHERE id=?", (ticket_id,)).fetchone()
        return Ticket.from_dict(json.loads(r["data"])) if r else None

    def tickets_for(self, account_id: str) -> list[Ticket]:
        rows = self._conn.execute("SELECT data FROM ticket WHERE account_id=? ORDER BY rowid",
                                  (account_id,)).fetchall()
        return [Ticket.from_dict(json.loads(r["data"])) for r in rows]

    def ticket_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM ticket WHERE status=?", (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM ticket").fetchone()["c"]

    # -- feedback -------------------------------------------------------- #
    def put_feedback(self, f: Feedback) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO feedback (id, account_id, score, data) VALUES (?, ?, ?, ?)",
                (f.id, f.account_id, f.score, json.dumps(f.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def feedback_for(self, account_id: str) -> list[Feedback]:
        rows = self._conn.execute("SELECT data FROM feedback WHERE account_id=? ORDER BY rowid",
                                  (account_id,)).fetchall()
        return [Feedback.from_dict(json.loads(r["data"])) for r in rows]

    def feedback_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM feedback").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["CustomerRepository"]
