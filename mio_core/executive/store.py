"""MIO Core · E1 — Persistent Executive State: kalıcılık adaptörü (storage-agnostik).

`ExecutiveStateStore` protokolü, Executive State'in fiziksel depodan BAĞIMSIZ olmasını sağlar
(MongoDB [MarkaAsistan], SQLite [MIO Beyin] ya da başka — hepsi aynı sözleşmeyi uygular). Bu, "fiziksel
yapı sonra" ilkesini korur ve E1 mantığının saf/deterministik kalmasını sağlar.

`SQLiteExecutiveStateStore` üretim-kalite referans implementasyondur: stdlib sqlite3, WAL, parametreli
sorgular, thread-güvenli yazım. Placeholder/mock YOKTUR — gerçek kalıcılık.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional, Protocol, runtime_checkable

from .models import Decision, GoalRef, Identity, Lesson, Mission, Purpose, Strategy

__all__ = ["ExecutiveStateStore", "SQLiteExecutiveStateStore"]


@runtime_checkable
class ExecutiveStateStore(Protocol):
    """Executive State kalıcılık sözleşmesi. Herhangi bir depo bunu uygular."""

    # Kimlik / Misyon / Purpose (tekil)
    def get_identity(self) -> Optional[Identity]: ...
    def put_identity(self, identity: Identity) -> None: ...
    def get_mission(self) -> Optional[Mission]: ...
    def put_mission(self, mission: Mission) -> None: ...
    def get_purpose(self) -> Optional[Purpose]: ...
    def put_purpose(self, purpose: Purpose) -> None: ...

    # Hedef referansları
    def list_goal_refs(self, status: Optional[str] = None) -> list[GoalRef]: ...
    def put_goal_ref(self, ref: GoalRef) -> None: ...
    def remove_goal_ref(self, goal_id: str) -> None: ...

    # Stratejiler
    def get_active_strategy(self, goal_id: str) -> Optional[Strategy]: ...
    def list_strategies(self, goal_id: Optional[str] = None,
                        status: Optional[str] = None) -> list[Strategy]: ...
    def put_strategy(self, strategy: Strategy) -> None: ...

    # Karar defteri
    def append_decision(self, decision: Decision) -> None: ...
    def update_decision(self, decision: Decision) -> None: ...
    def get_decision(self, decision_id: str) -> Optional[Decision]: ...
    def list_decisions(self, limit: int = 50, status: Optional[str] = None) -> list[Decision]: ...

    # Dersler
    def append_lesson(self, lesson: Lesson) -> None: ...
    def find_lessons(self, keywords: list[str], limit: int = 20) -> list[Lesson]: ...
    def list_lessons(self, limit: int = 100) -> list[Lesson]: ...

    def close(self) -> None: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS executive_singletons (
    key  TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS goal_refs (
    goal_id TEXT PRIMARY KEY,
    status  TEXT NOT NULL DEFAULT 'active',
    data    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategies (
    id        TEXT PRIMARY KEY,
    goal_id   TEXT NOT NULL,
    status    TEXT NOT NULL DEFAULT 'active',
    chosen_at TEXT NOT NULL,
    data      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_strategies_goal ON strategies(goal_id, status);
CREATE TABLE IF NOT EXISTS decisions (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_decisions_created ON decisions(created_at DESC);
CREATE TABLE IF NOT EXISTS lessons (
    id         TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    text       TEXT NOT NULL,
    applies_to TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    data       TEXT NOT NULL
);
"""


class SQLiteExecutiveStateStore:
    """Üretim-kalite SQLite referans deposu. stdlib-only, thread-güvenli."""

    def __init__(self, path: str = "mio_executive_state.db") -> None:
        self._path = str(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- Kimlik / Misyon ---------------------------------------------------- #
    def _get_singleton(self, key: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT data FROM executive_singletons WHERE key = ?", (key,)).fetchone()
        return json.loads(row["data"]) if row else None

    def _put_singleton(self, key: str, data: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO executive_singletons (key, data) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET data = excluded.data",
                (key, json.dumps(data, ensure_ascii=False)))
            self._conn.commit()

    def get_identity(self) -> Optional[Identity]:
        d = self._get_singleton("identity")
        return Identity.from_dict(d) if d else None

    def put_identity(self, identity: Identity) -> None:
        self._put_singleton("identity", identity.to_dict())

    def get_mission(self) -> Optional[Mission]:
        d = self._get_singleton("mission")
        return Mission.from_dict(d) if d else None

    def put_mission(self, mission: Mission) -> None:
        self._put_singleton("mission", mission.to_dict())

    def get_purpose(self) -> Optional[Purpose]:
        d = self._get_singleton("purpose")
        return Purpose.from_dict(d) if d else None

    def put_purpose(self, purpose: Purpose) -> None:
        self._put_singleton("purpose", purpose.to_dict())

    # -- Hedef referansları ------------------------------------------------- #
    def list_goal_refs(self, status: Optional[str] = None) -> list[GoalRef]:
        if status:
            rows = self._conn.execute(
                "SELECT data FROM goal_refs WHERE status = ? ORDER BY goal_id", (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM goal_refs ORDER BY goal_id").fetchall()
        return [GoalRef.from_dict(json.loads(r["data"])) for r in rows]

    def put_goal_ref(self, ref: GoalRef) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO goal_refs (goal_id, status, data) VALUES (?, ?, ?) "
                "ON CONFLICT(goal_id) DO UPDATE SET status = excluded.status, data = excluded.data",
                (ref.goal_id, ref.status, json.dumps(ref.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def remove_goal_ref(self, goal_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM goal_refs WHERE goal_id = ?", (goal_id,))
            self._conn.commit()

    # -- Stratejiler -------------------------------------------------------- #
    def get_active_strategy(self, goal_id: str) -> Optional[Strategy]:
        row = self._conn.execute(
            "SELECT data FROM strategies WHERE goal_id = ? AND status = 'active' "
            "ORDER BY chosen_at DESC LIMIT 1", (goal_id,)).fetchone()
        return Strategy.from_dict(json.loads(row["data"])) if row else None

    def list_strategies(self, goal_id: Optional[str] = None,
                        status: Optional[str] = None) -> list[Strategy]:
        clauses, params = [], []
        if goal_id:
            clauses.append("goal_id = ?"); params.append(goal_id)
        if status:
            clauses.append("status = ?"); params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT data FROM strategies{where} ORDER BY chosen_at DESC", params).fetchall()
        return [Strategy.from_dict(json.loads(r["data"])) for r in rows]

    def put_strategy(self, strategy: Strategy) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO strategies (id, goal_id, status, chosen_at, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status = excluded.status, data = excluded.data",
                (strategy.id, strategy.goal_id, strategy.status.value, strategy.chosen_at,
                 json.dumps(strategy.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    # -- Karar defteri (append-only + zincir güncellemesi) ------------------ #
    def append_decision(self, decision: Decision) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO decisions (id, kind, status, created_at, data) VALUES (?, ?, ?, ?, ?)",
                (decision.id, decision.kind, decision.status.value, decision.created_at,
                 json.dumps(decision.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def update_decision(self, decision: Decision) -> None:
        """Yalnız zincir/durum güncellemesi (outcome/prediction_error/belief_update, DEFER→committed).
        Kararın kendisi silinmez; gerekçe ve geçmiş korunur."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE decisions SET status = ?, data = ? WHERE id = ?",
                (decision.status.value, json.dumps(decision.to_dict(), ensure_ascii=False), decision.id))
            self._conn.commit()
            if cur.rowcount == 0:
                raise KeyError(f"Karar bulunamadı: {decision.id}")

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        row = self._conn.execute(
            "SELECT data FROM decisions WHERE id = ?", (decision_id,)).fetchone()
        return Decision.from_dict(json.loads(row["data"])) if row else None

    def list_decisions(self, limit: int = 50, status: Optional[str] = None) -> list[Decision]:
        if status:
            rows = self._conn.execute(
                "SELECT data FROM decisions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT data FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [Decision.from_dict(json.loads(r["data"])) for r in rows]

    # -- Dersler ------------------------------------------------------------ #
    def append_lesson(self, lesson: Lesson) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO lessons (id, source, text, applies_to, created_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (lesson.id, lesson.source, lesson.text, " ".join(lesson.applies_to),
                 lesson.created_at, json.dumps(lesson.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def find_lessons(self, keywords: list[str], limit: int = 20) -> list[Lesson]:
        """Deterministik ilgi araması: text ya da applies_to bir anahtar kelimeyi içeren dersler,
        eşleşme sayısına göre sıralı. Uydurma/embedding yok — yalın, açıklanabilir."""
        kws = [k.strip().lower() for k in keywords if k and k.strip()]
        if not kws:
            return []
        rows = self._conn.execute("SELECT text, applies_to, data FROM lessons").fetchall()
        scored: list[tuple[int, Lesson]] = []
        for r in rows:
            hay = (r["text"] + " " + (r["applies_to"] or "")).lower()
            score = sum(1 for k in kws if k in hay)
            if score:
                scored.append((score, Lesson.from_dict(json.loads(r["data"]))))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [ls for _, ls in scored[:limit]]

    def list_lessons(self, limit: int = 100) -> list[Lesson]:
        rows = self._conn.execute(
            "SELECT data FROM lessons ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [Lesson.from_dict(json.loads(r["data"])) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
