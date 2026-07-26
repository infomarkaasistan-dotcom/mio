"""MIO Core · Planning Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Plan

_SCHEMA = """
CREATE TABLE IF NOT EXISTS plan (
    id TEXT PRIMARY KEY, objective TEXT NOT NULL, goal_id TEXT, status TEXT NOT NULL,
    updated_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_plan_status ON plan(status);
CREATE INDEX IF NOT EXISTS ix_plan_goal ON plan(goal_id);
"""


class PlanRepository:
    def __init__(self, path: str = "mio_plans.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, plan: Plan) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO plan (id, objective, goal_id, status, updated_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET objective=excluded.objective, "
                "goal_id=excluded.goal_id, status=excluded.status, updated_at=excluded.updated_at, "
                "data=excluded.data",
                (plan.id, plan.objective, plan.goal_id, plan.status, plan.updated_at,
                 json.dumps(plan.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, plan_id: str) -> Optional[Plan]:
        r = self._conn.execute("SELECT data FROM plan WHERE id=?", (plan_id,)).fetchone()
        return Plan.from_dict(json.loads(r["data"])) if r else None

    def list(self, *, status: Optional[str] = None, goal_id: Optional[str] = None) -> list[Plan]:
        q, args = "SELECT data FROM plan", []
        conds = []
        if status:
            conds.append("status=?"); args.append(status)
        if goal_id:
            conds.append("goal_id=?"); args.append(goal_id)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY rowid"
        return [Plan.from_dict(json.loads(r["data"])) for r in self._conn.execute(q, args).fetchall()]

    def delete(self, plan_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM plan WHERE id=?", (plan_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def count(self, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM plan WHERE status=?", (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM plan").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["PlanRepository"]
