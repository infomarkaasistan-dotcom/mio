"""MIO Core · Distributed Execution Domain — Repository (SQLite, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import DistributedJob, JobStatus, Node

_SCHEMA = """
CREATE TABLE IF NOT EXISTS node (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dist_job (
    id TEXT PRIMARY KEY, status TEXT NOT NULL, assigned_node TEXT NOT NULL,
    idempotency_key TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_djob_status ON dist_job(status);
CREATE INDEX IF NOT EXISTS ix_djob_node ON dist_job(assigned_node, status);
CREATE INDEX IF NOT EXISTS ix_djob_idem ON dist_job(idempotency_key);
"""


class DistExecRepository:
    def __init__(self, path: str = "mio_dist_exec.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- nodes ----------------------------------------------------------- #
    def put_node(self, n: Node) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO node (id, name, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, status=excluded.status, data=excluded.data",
                (n.id, n.name, n.status, json.dumps(n.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_node(self, node_id: str) -> Optional[Node]:
        r = self._conn.execute("SELECT data FROM node WHERE id=?", (node_id,)).fetchone()
        return Node.from_dict(json.loads(r["data"])) if r else None

    def all_nodes(self) -> list[Node]:
        rows = self._conn.execute("SELECT data FROM node ORDER BY rowid").fetchall()
        return [Node.from_dict(json.loads(r["data"])) for r in rows]

    def node_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM node").fetchone()["c"]

    def active_load(self, node_id: str) -> int:
        marks = tuple(JobStatus.ACTIVE_LOAD)
        q = ("SELECT COUNT(*) c FROM dist_job WHERE assigned_node=? AND status IN "
             f"({','.join('?' * len(marks))})")
        return self._conn.execute(q, (node_id, *marks)).fetchone()["c"]

    # -- jobs ------------------------------------------------------------ #
    def put_job(self, j: DistributedJob) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO dist_job (id, status, assigned_node, idempotency_key, data) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
                "assigned_node=excluded.assigned_node, data=excluded.data",
                (j.id, j.status, j.assigned_node, j.idempotency_key,
                 json.dumps(j.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_job(self, job_id: str) -> Optional[DistributedJob]:
        r = self._conn.execute("SELECT data FROM dist_job WHERE id=?", (job_id,)).fetchone()
        return DistributedJob.from_dict(json.loads(r["data"])) if r else None

    def find_by_idempotency(self, key: str) -> list[DistributedJob]:
        rows = self._conn.execute("SELECT data FROM dist_job WHERE idempotency_key=? ORDER BY rowid",
                                  (key,)).fetchall()
        return [DistributedJob.from_dict(json.loads(r["data"])) for r in rows]

    def all_jobs(self, *, status: Optional[str] = None) -> list[DistributedJob]:
        if status:
            rows = self._conn.execute("SELECT data FROM dist_job WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM dist_job ORDER BY rowid").fetchall()
        return [DistributedJob.from_dict(json.loads(r["data"])) for r in rows]

    def job_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM dist_job WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM dist_job").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["DistExecRepository"]
