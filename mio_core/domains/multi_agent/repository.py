"""MIO Core · Multi-Agent Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Agent, AgentTask, TaskStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_task (
    id TEXT PRIMARY KEY, status TEXT NOT NULL, assigned_agent TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_task_status ON agent_task(status);
CREATE INDEX IF NOT EXISTS ix_task_agent ON agent_task(assigned_agent, status);
"""


class MultiAgentRepository:
    def __init__(self, path: str = "mio_multi_agent.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- agents ---------------------------------------------------------- #
    def put_agent(self, a: Agent) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO agent (id, name, role, status, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, role=excluded.role, "
                "status=excluded.status, data=excluded.data",
                (a.id, a.name, a.role, a.status, json.dumps(a.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        r = self._conn.execute("SELECT data FROM agent WHERE id=?", (agent_id,)).fetchone()
        return Agent.from_dict(json.loads(r["data"])) if r else None

    def all_agents(self) -> list[Agent]:
        rows = self._conn.execute("SELECT data FROM agent ORDER BY rowid").fetchall()
        return [Agent.from_dict(json.loads(r["data"])) for r in rows]

    def agent_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM agent").fetchone()["c"]

    def active_load(self, agent_id: str) -> int:
        """Agent'ın şu an aktif yükü (assigned/working görev sayısı)."""
        marks = tuple(TaskStatus.ACTIVE_LOAD)
        q = ("SELECT COUNT(*) c FROM agent_task WHERE assigned_agent=? AND status IN "
             f"({','.join('?' * len(marks))})")
        return self._conn.execute(q, (agent_id, *marks)).fetchone()["c"]

    # -- tasks ----------------------------------------------------------- #
    def put_task(self, t: AgentTask) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO agent_task (id, status, assigned_agent, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
                "assigned_agent=excluded.assigned_agent, data=excluded.data",
                (t.id, t.status, t.assigned_agent, json.dumps(t.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        r = self._conn.execute("SELECT data FROM agent_task WHERE id=?", (task_id,)).fetchone()
        return AgentTask.from_dict(json.loads(r["data"])) if r else None

    def all_tasks(self, *, status: Optional[str] = None) -> list[AgentTask]:
        if status:
            rows = self._conn.execute("SELECT data FROM agent_task WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM agent_task ORDER BY rowid").fetchall()
        return [AgentTask.from_dict(json.loads(r["data"])) for r in rows]

    def task_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM agent_task WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM agent_task").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["MultiAgentRepository"]
