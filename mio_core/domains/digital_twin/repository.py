"""MIO Core · Digital Twin Domain — Repository (SQLite, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import SimulationRun, Twin

_SCHEMA = """
CREATE TABLE IF NOT EXISTS twin (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sim_run (
    id TEXT PRIMARY KEY, twin_id TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_simrun_twin ON sim_run(twin_id, status);
"""


class DigitalTwinRepository:
    def __init__(self, path: str = "mio_digital_twin.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- twins ----------------------------------------------------------- #
    def put_twin(self, t: Twin) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO twin (id, name, kind, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, kind=excluded.kind, data=excluded.data",
                (t.id, t.name, t.kind, json.dumps(t.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_twin(self, twin_id: str) -> Optional[Twin]:
        r = self._conn.execute("SELECT data FROM twin WHERE id=?", (twin_id,)).fetchone()
        return Twin.from_dict(json.loads(r["data"])) if r else None

    def all_twins(self) -> list[Twin]:
        rows = self._conn.execute("SELECT data FROM twin ORDER BY rowid").fetchall()
        return [Twin.from_dict(json.loads(r["data"])) for r in rows]

    def twin_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM twin").fetchone()["c"]

    # -- simulation runs ------------------------------------------------- #
    def put_run(self, r: SimulationRun) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO sim_run (id, twin_id, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (r.id, r.twin_id, r.status, json.dumps(r.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_run(self, run_id: str) -> Optional[SimulationRun]:
        r = self._conn.execute("SELECT data FROM sim_run WHERE id=?", (run_id,)).fetchone()
        return SimulationRun.from_dict(json.loads(r["data"])) if r else None

    def runs_for(self, twin_id: str) -> list[SimulationRun]:
        rows = self._conn.execute("SELECT data FROM sim_run WHERE twin_id=? ORDER BY rowid",
                                  (twin_id,)).fetchall()
        return [SimulationRun.from_dict(json.loads(r["data"])) for r in rows]

    def all_runs(self, *, status: Optional[str] = None) -> list[SimulationRun]:
        if status:
            rows = self._conn.execute("SELECT data FROM sim_run WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM sim_run ORDER BY rowid").fetchall()
        return [SimulationRun.from_dict(json.loads(r["data"])) for r in rows]

    def run_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM sim_run").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["DigitalTwinRepository"]
