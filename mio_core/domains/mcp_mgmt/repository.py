"""MIO Core · MCP Management — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ.

MCP sunucu kaydını (restart'ta hub'a geri yüklenir) ve append-only lifecycle denetimini tutar."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional
from uuid import uuid4

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mcp_server (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, transport TEXT NOT NULL DEFAULT 'stdio',
    trust_level TEXT NOT NULL DEFAULT 'untrusted', status TEXT NOT NULL DEFAULT 'unknown',
    updated_at TEXT NOT NULL DEFAULT '', data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mcp_lifecycle (
    id TEXT PRIMARY KEY, server TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
    at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_mcplc_server ON mcp_lifecycle(server);
"""


class MCPRepository:
    def __init__(self, path: str = "mio_mcp.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put_server(self, server_dict: dict, updated_at: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO mcp_server (id, name, transport, trust_level, status, updated_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, "
                "transport=excluded.transport, trust_level=excluded.trust_level, status=excluded.status, "
                "updated_at=excluded.updated_at, data=excluded.data",
                (server_dict["id"], server_dict["name"], server_dict.get("transport", "stdio"),
                 server_dict.get("trust_level", "untrusted"), server_dict.get("status", "unknown"),
                 updated_at, json.dumps(server_dict, ensure_ascii=False)))
            self._conn.commit()

    def get_server(self, server_id: str) -> Optional[dict]:
        r = self._conn.execute("SELECT data FROM mcp_server WHERE id=?", (server_id,)).fetchone()
        return json.loads(r["data"]) if r else None

    def all_servers(self) -> list[dict]:
        rows = self._conn.execute("SELECT data FROM mcp_server ORDER BY rowid").fetchall()
        return [json.loads(r["data"]) for r in rows]

    def delete_server(self, server_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM mcp_server WHERE id=?", (server_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def count_servers(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM mcp_server").fetchone()["c"]

    def append_lifecycle(self, server: str, kind: str, detail: str, at: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO mcp_lifecycle (id, server, kind, detail, at) VALUES (?, ?, ?, ?, ?)",
                (uuid4().hex[:16], server, kind, detail, at))
            self._conn.commit()

    def lifecycle_recent(self, limit: int = 100, *, server: Optional[str] = None) -> list[dict]:
        if server:
            rows = self._conn.execute("SELECT server, kind, detail, at FROM mcp_lifecycle WHERE server=? "
                                      "ORDER BY rowid DESC LIMIT ?", (server, limit)).fetchall()
        else:
            rows = self._conn.execute("SELECT server, kind, detail, at FROM mcp_lifecycle "
                                      "ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["MCPRepository"]
