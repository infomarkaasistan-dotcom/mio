"""MIO Core · Marketing & Growth — Repository (SQLite, kalıcı, write-through), stdlib-only, LLM-BAĞIMSIZ."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from .models import Campaign

_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, channel TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_camp_channel ON campaign(channel);
"""


class MarketingRepository:
    def __init__(self, path: str = "mio_marketing.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, c: Campaign) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO campaign (id, name, channel, status, data) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, channel=excluded.channel, "
                "status=excluded.status, data=excluded.data",
                (c.id, c.name, c.channel, c.status, json.dumps(c.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, campaign_id: str) -> Optional[Campaign]:
        r = self._conn.execute("SELECT data FROM campaign WHERE id=?", (campaign_id,)).fetchone()
        return Campaign.from_dict(json.loads(r["data"])) if r else None

    def all(self, *, channel: Optional[str] = None) -> list[Campaign]:
        if channel:
            rows = self._conn.execute("SELECT data FROM campaign WHERE channel=? ORDER BY rowid",
                                      (channel,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM campaign ORDER BY rowid").fetchall()
        return [Campaign.from_dict(json.loads(r["data"])) for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM campaign").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["MarketingRepository"]
