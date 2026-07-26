"""MIO Core · Federation Domain — Repository (SQLite, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Peer, ShareJob

_SCHEMA = """
CREATE TABLE IF NOT EXISTS peer (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS share_job (
    id TEXT PRIMARY KEY, peer_id TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_peer_status ON peer(status);
CREATE INDEX IF NOT EXISTS ix_share_status ON share_job(status);
"""


class FederationRepository:
    def __init__(self, path: str = "mio_federation.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- peers ----------------------------------------------------------- #
    def put_peer(self, p: Peer) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO peer (id, name, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, status=excluded.status, data=excluded.data",
                (p.id, p.name, p.status, json.dumps(p.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_peer(self, peer_id: str) -> Optional[Peer]:
        r = self._conn.execute("SELECT data FROM peer WHERE id=?", (peer_id,)).fetchone()
        return Peer.from_dict(json.loads(r["data"])) if r else None

    def all_peers(self, *, status: Optional[str] = None) -> list[Peer]:
        if status:
            rows = self._conn.execute("SELECT data FROM peer WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM peer ORDER BY rowid").fetchall()
        return [Peer.from_dict(json.loads(r["data"])) for r in rows]

    def peer_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM peer WHERE status=?", (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM peer").fetchone()["c"]

    # -- share jobs ------------------------------------------------------ #
    def put_share(self, s: ShareJob) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO share_job (id, peer_id, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
                (s.id, s.peer_id, s.status, json.dumps(s.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get_share(self, share_id: str) -> Optional[ShareJob]:
        r = self._conn.execute("SELECT data FROM share_job WHERE id=?", (share_id,)).fetchone()
        return ShareJob.from_dict(json.loads(r["data"])) if r else None

    def all_shares(self, *, status: Optional[str] = None) -> list[ShareJob]:
        if status:
            rows = self._conn.execute("SELECT data FROM share_job WHERE status=? ORDER BY rowid",
                                      (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM share_job ORDER BY rowid").fetchall()
        return [ShareJob.from_dict(json.loads(r["data"])) for r in rows]

    def share_count(self, *, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute("SELECT COUNT(*) c FROM share_job WHERE status=?",
                                      (status,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM share_job").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["FederationRepository"]
