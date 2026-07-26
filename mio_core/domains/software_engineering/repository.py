"""MIO Core · Software Engineering — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

Artifact ve engineering-task kayıtlarını tutar."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Artifact, EngTask

_SCHEMA = """
CREATE TABLE IF NOT EXISTS se_artifact (
    id TEXT PRIMARY KEY, path TEXT NOT NULL, kind TEXT NOT NULL, language TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS se_task (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
    artifact_id TEXT, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_setask_status ON se_task(status);
"""


class SoftwareRepository:
    def __init__(self, path: str = "mio_software.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- artifacts ------------------------------------------------------- #
    def put_artifact(self, a: Artifact) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO se_artifact (id, path, kind, language, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET path=excluded.path, kind=excluded.kind, "
                "language=excluded.language, data=excluded.data",
                (a.id, a.path, a.kind, a.language, json.dumps(a.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        r = self._conn.execute("SELECT data FROM se_artifact WHERE id=?", (artifact_id,)).fetchone()
        return Artifact.from_dict(json.loads(r["data"])) if r else None

    def all_artifacts(self) -> list[Artifact]:
        rows = self._conn.execute("SELECT data FROM se_artifact ORDER BY rowid").fetchall()
        return [Artifact.from_dict(json.loads(r["data"])) for r in rows]

    def artifact_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM se_artifact").fetchone()["c"]

    # -- tasks ----------------------------------------------------------- #
    def put_task(self, t: EngTask) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO se_task (id, title, kind, status, artifact_id, data) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, kind=excluded.kind, "
                "status=excluded.status, artifact_id=excluded.artifact_id, data=excluded.data",
                (t.id, t.title, t.kind, t.status, t.artifact_id, json.dumps(t.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_task(self, task_id: str) -> Optional[EngTask]:
        r = self._conn.execute("SELECT data FROM se_task WHERE id=?", (task_id,)).fetchone()
        return EngTask.from_dict(json.loads(r["data"])) if r else None

    def list_tasks(self, *, status: Optional[str] = None, kind: Optional[str] = None) -> list[EngTask]:
        q, args, conds = "SELECT data FROM se_task", [], []
        if status:
            conds.append("status=?"); args.append(status)
        if kind:
            conds.append("kind=?"); args.append(kind)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY rowid"
        return [EngTask.from_dict(json.loads(r["data"])) for r in self._conn.execute(q, args).fetchall()]

    def task_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM se_task WHERE status=?", (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM se_task").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["SoftwareRepository"]
