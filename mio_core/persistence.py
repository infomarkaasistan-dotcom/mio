"""MIO Core · Persistence (Area 3) — hafif JSON-KV kalıcılık (SQLite), LLM-BAĞIMSIZ, stdlib-only.

Yaşayarak öğrenilen bilgi (KnowledgeBase learned) + kullanım metrikleri (Meta) yeniden başlatmada kaybolmasın.
Mevcut servislerin arayüzü arkasında; opsiyonel (yoksa in-memory, backward-compatible). Çekirdek büyümez."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any


class JsonKVStore:
    """key → JSON. Snapshot/restore için (boot'ta yükle, close'da yaz)."""

    def __init__(self, path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
        self._conn.commit()

    def get(self, key: str, default: Any = None) -> Any:
        r = self._conn.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                (key, json.dumps(value, ensure_ascii=False)))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = ["JsonKVStore"]
