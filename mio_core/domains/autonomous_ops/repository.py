"""MIO Core · Autonomous Operations Domain — Repository (SQLite, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import OpsRule, Proposal

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ops_rule (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, metric TEXT NOT NULL, enabled INTEGER NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proposal (
    id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_rule_metric ON ops_rule(metric, enabled);
CREATE INDEX IF NOT EXISTS ix_proposal_status ON proposal(status);
"""


class AutoOpsRepository:
    def __init__(self, path: str = "mio_autonomous_ops.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- rules ----------------------------------------------------------- #
    def put_rule(self, r: OpsRule) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO ops_rule (id, name, metric, enabled, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, metric=excluded.metric, "
                "enabled=excluded.enabled, data=excluded.data",
                (r.id, r.name, r.metric, 1 if r.enabled else 0,
                 json.dumps(r.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_rule(self, rule_id: str) -> Optional[OpsRule]:
        r = self._conn.execute("SELECT data FROM ops_rule WHERE id=?", (rule_id,)).fetchone()
        return OpsRule.from_dict(json.loads(r["data"])) if r else None

    def rules_for(self, metric: str) -> list[OpsRule]:
        rows = self._conn.execute(
            "SELECT data FROM ops_rule WHERE metric=? AND enabled=1 ORDER BY rowid", (metric,)).fetchall()
        return [OpsRule.from_dict(json.loads(r["data"])) for r in rows]

    def all_rules(self) -> list[OpsRule]:
        rows = self._conn.execute("SELECT data FROM ops_rule ORDER BY rowid").fetchall()
        return [OpsRule.from_dict(json.loads(r["data"])) for r in rows]

    def rule_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM ops_rule").fetchone()["c"]

    # -- proposals ------------------------------------------------------- #
    def put_proposal(self, p: Proposal) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO proposal (id, rule_id, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (p.id, p.rule_id, p.status, json.dumps(p.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        r = self._conn.execute("SELECT data FROM proposal WHERE id=?", (proposal_id,)).fetchone()
        return Proposal.from_dict(json.loads(r["data"])) if r else None

    def all_proposals(self, *, status: Optional[str] = None) -> list[Proposal]:
        if status:
            rows = self._conn.execute("SELECT data FROM proposal WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM proposal ORDER BY rowid").fetchall()
        return [Proposal.from_dict(json.loads(r["data"])) for r in rows]

    def proposal_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM proposal WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM proposal").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["AutoOpsRepository"]
