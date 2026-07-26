"""MIO Core · IoT Domain — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Alert, AlertRule, CommandJob, Reading, Thing

_SCHEMA = """
CREATE TABLE IF NOT EXISTS thing (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, protocol TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reading (
    id TEXT PRIMARY KEY, thing_id TEXT NOT NULL, metric TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alert_rule (
    id TEXT PRIMARY KEY, thing_id TEXT NOT NULL, metric TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alert (
    id TEXT PRIMARY KEY, thing_id TEXT NOT NULL, rule_id TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS iot_command (
    id TEXT PRIMARY KEY, thing_id TEXT NOT NULL, status TEXT NOT NULL, risk TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_reading_thing ON reading(thing_id, metric);
CREATE INDEX IF NOT EXISTS ix_rule_thing ON alert_rule(thing_id, metric);
CREATE INDEX IF NOT EXISTS ix_iotcmd_status ON iot_command(status);
"""


class IoTRepository:
    def __init__(self, path: str = "mio_iot.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- things ---------------------------------------------------------- #
    def put_thing(self, t: Thing) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO thing (id, name, kind, protocol, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
                "protocol=excluded.protocol, data=excluded.data",
                (t.id, t.name, t.kind, t.protocol, json.dumps(t.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_thing(self, thing_id: str) -> Optional[Thing]:
        r = self._conn.execute("SELECT data FROM thing WHERE id=?", (thing_id,)).fetchone()
        return Thing.from_dict(json.loads(r["data"])) if r else None

    def all_things(self) -> list[Thing]:
        rows = self._conn.execute("SELECT data FROM thing ORDER BY rowid").fetchall()
        return [Thing.from_dict(json.loads(r["data"])) for r in rows]

    def thing_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM thing").fetchone()["c"]

    # -- readings -------------------------------------------------------- #
    def put_reading(self, r: Reading) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO reading (id, thing_id, metric, data) VALUES (?, ?, ?, ?)",
                (r.id, r.thing_id, r.metric, json.dumps(r.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def readings(self, thing_id: str, *, metric: Optional[str] = None, limit: int = 100) -> list[Reading]:
        if metric:
            rows = self._conn.execute(
                "SELECT data FROM reading WHERE thing_id=? AND metric=? ORDER BY rowid DESC LIMIT ?",
                (thing_id, metric, int(limit))).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT data FROM reading WHERE thing_id=? ORDER BY rowid DESC LIMIT ?",
                (thing_id, int(limit))).fetchall()
        return [Reading.from_dict(json.loads(x["data"])) for x in rows]

    def latest_reading(self, thing_id: str, metric: str) -> Optional[Reading]:
        r = self._conn.execute(
            "SELECT data FROM reading WHERE thing_id=? AND metric=? ORDER BY rowid DESC LIMIT 1",
            (thing_id, metric)).fetchone()
        return Reading.from_dict(json.loads(r["data"])) if r else None

    def reading_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM reading").fetchone()["c"]

    # -- alert rules ----------------------------------------------------- #
    def put_rule(self, rule: AlertRule) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO alert_rule (id, thing_id, metric, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (rule.id, rule.thing_id, rule.metric, json.dumps(rule.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def rules_for(self, thing_id: str, metric: str) -> list[AlertRule]:
        rows = self._conn.execute(
            "SELECT data FROM alert_rule WHERE thing_id=? AND metric=? ORDER BY rowid",
            (thing_id, metric)).fetchall()
        return [AlertRule.from_dict(json.loads(r["data"])) for r in rows]

    def all_rules(self) -> list[AlertRule]:
        rows = self._conn.execute("SELECT data FROM alert_rule ORDER BY rowid").fetchall()
        return [AlertRule.from_dict(json.loads(r["data"])) for r in rows]

    def rule_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM alert_rule").fetchone()["c"]

    # -- alerts ---------------------------------------------------------- #
    def put_alert(self, a: Alert) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO alert (id, thing_id, rule_id, data) VALUES (?, ?, ?, ?)",
                (a.id, a.thing_id, a.rule_id, json.dumps(a.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def all_alerts(self, *, thing_id: Optional[str] = None) -> list[Alert]:
        if thing_id:
            rows = self._conn.execute("SELECT data FROM alert WHERE thing_id=? ORDER BY rowid DESC",
                                      (thing_id,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM alert ORDER BY rowid DESC").fetchall()
        return [Alert.from_dict(json.loads(r["data"])) for r in rows]

    def alert_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM alert").fetchone()["c"]

    # -- commands -------------------------------------------------------- #
    def put_command(self, j: CommandJob) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO iot_command (id, thing_id, status, risk, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (j.id, j.thing_id, j.status, j.risk, json.dumps(j.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_command(self, job_id: str) -> Optional[CommandJob]:
        r = self._conn.execute("SELECT data FROM iot_command WHERE id=?", (job_id,)).fetchone()
        return CommandJob.from_dict(json.loads(r["data"])) if r else None

    def all_commands(self, *, status: Optional[str] = None) -> list[CommandJob]:
        if status:
            rows = self._conn.execute("SELECT data FROM iot_command WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM iot_command ORDER BY rowid").fetchall()
        return [CommandJob.from_dict(json.loads(r["data"])) for r in rows]

    def command_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM iot_command WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM iot_command").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["IoTRepository"]
