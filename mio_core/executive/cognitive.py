"""MIO Core · E5 — Cognitive Engine (yaşayan zihin çekirdeği), LLM-BAĞIMSIZ.

MIO'nun inançlarını (gerçekliği yorumlama biçimi) tutar: her inanç bir konu (subject), ifade, alan
(world/business/strategy/self...), güven ve valans taşır. Zıt kanıt gelince mevcut inanç SESSİZCE EZİLMEZ —
revizyon için işaretlenir (çelişki 1. sınıf). Tahmin-hatası bir inancı çürütünce de işaretlenir.

Born Capable (ADR-0001): `born_with(...)` ile innate inançlarla (temel dünya/işletme/strateji bilgisi)
DOĞAR — boş değil. Bu innate bilgi deneyim değil, eğitilmiş başlangıç çekirdeğidir (source="innate").

E5, E3'ün **BeliefSource** adaptörüdür: `flagged_for_revision()` + `mark_revised()`. Böylece "inançlarım
hâlâ doğru mu?" öz-sorgusu (Belief Revision) E3→E4→E1 zincirinden geçer. Deterministik; LLM çağırmaz.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from .models import new_id, now_iso

__all__ = ["Belief", "BeliefStore", "SQLiteBeliefStore", "CognitiveEngine"]

_SIGNIFICANT_OPPOSITION = 1.0     # |v_yeni - v_mevcut| bu eşiği aşan zıt valans → çelişki


@dataclass
class Belief:
    subject: str
    statement: str
    domain: str = "world"
    confidence: float = 0.6
    valence: float = 0.0                          # [-1,1] — inancın yönü/kutbu
    source: str = "observation"                   # innate | observation | inference | owner
    status: str = "active"                        # active | revised
    flagged_for_revision: bool = False
    revision_reason: str = ""
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "subject": self.subject, "statement": self.statement,
                "domain": self.domain, "confidence": self.confidence, "valence": self.valence,
                "source": self.source, "status": self.status,
                "flagged_for_revision": self.flagged_for_revision,
                "revision_reason": self.revision_reason,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Belief":
        return cls(subject=d["subject"], statement=d["statement"], domain=d.get("domain", "world"),
                   confidence=float(d.get("confidence", 0.6)), valence=float(d.get("valence", 0.0)),
                   source=d.get("source", "observation"), status=d.get("status", "active"),
                   flagged_for_revision=bool(d.get("flagged_for_revision", False)),
                   revision_reason=d.get("revision_reason", ""), id=d.get("id") or new_id(),
                   created_at=d.get("created_at") or now_iso(), updated_at=d.get("updated_at") or now_iso())


@runtime_checkable
class BeliefStore(Protocol):
    def put(self, belief: Belief) -> None: ...
    def get(self, belief_id: str) -> Optional[Belief]: ...
    def list(self, domain: Optional[str] = None, status: Optional[str] = None) -> list[Belief]: ...
    def list_flagged(self) -> list[Belief]: ...
    def list_by_subject(self, subject: str, status: str = "active") -> list[Belief]: ...
    def count(self, source: Optional[str] = None) -> int: ...
    def close(self) -> None: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS beliefs (
    id      TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    domain  TEXT NOT NULL,
    status  TEXT NOT NULL,
    source  TEXT NOT NULL,
    flagged INTEGER NOT NULL DEFAULT 0,
    data    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_beliefs_subject ON beliefs(subject, status);
CREATE INDEX IF NOT EXISTS ix_beliefs_flagged ON beliefs(flagged);
"""


class SQLiteBeliefStore:
    """Üretim-kalite SQLite inanç deposu (E1 deseniyle aynı: stdlib, WAL, thread-güvenli)."""

    def __init__(self, path: str = "mio_cognitive.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def put(self, belief: Belief) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO beliefs (id, subject, domain, status, source, flagged, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "subject=excluded.subject, domain=excluded.domain, status=excluded.status, "
                "source=excluded.source, flagged=excluded.flagged, data=excluded.data",
                (belief.id, belief.subject, belief.domain, belief.status, belief.source,
                 1 if belief.flagged_for_revision else 0,
                 json.dumps(belief.to_dict(), ensure_ascii=False)))
            self._conn.commit()

    def get(self, belief_id: str) -> Optional[Belief]:
        row = self._conn.execute("SELECT data FROM beliefs WHERE id = ?", (belief_id,)).fetchone()
        return Belief.from_dict(json.loads(row["data"])) if row else None

    def list(self, domain: Optional[str] = None, status: Optional[str] = None) -> list[Belief]:
        clauses, params = [], []
        if domain:
            clauses.append("domain = ?"); params.append(domain)
        if status:
            clauses.append("status = ?"); params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(f"SELECT data FROM beliefs{where} ORDER BY rowid", params).fetchall()
        return [Belief.from_dict(json.loads(r["data"])) for r in rows]

    def list_flagged(self) -> list[Belief]:
        rows = self._conn.execute("SELECT data FROM beliefs WHERE flagged = 1 ORDER BY rowid").fetchall()
        return [Belief.from_dict(json.loads(r["data"])) for r in rows]

    def list_by_subject(self, subject: str, status: str = "active") -> list[Belief]:
        rows = self._conn.execute(
            "SELECT data FROM beliefs WHERE subject = ? AND status = ?", (subject, status)).fetchall()
        return [Belief.from_dict(json.loads(r["data"])) for r in rows]

    def count(self, source: Optional[str] = None) -> int:
        if source:
            return self._conn.execute("SELECT COUNT(*) c FROM beliefs WHERE source = ?", (source,)).fetchone()["c"]
        return self._conn.execute("SELECT COUNT(*) c FROM beliefs").fetchone()["c"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class CognitiveEngine:
    """E5 yaşayan zihin çekirdeği. Deterministik; LLM çağırmaz. E3'ün BeliefSource'u olarak çalışır."""

    def __init__(self, store: BeliefStore) -> None:
        self._store = store

    # -- Born Capable (ADR-0001) ------------------------------------------- #
    def born_with(self, seeds: list[dict[str, Any]]) -> int:
        """Innate inançlarla doğar (temel dünya/işletme/strateji bilgisi). Yalnız hiç innate inanç
        yoksa tohumlar (bir kez doğuş); tohumlanan sayısını döner. Deneyim değil — eğitilmiş çekirdek."""
        if self._store.count(source="innate") > 0:
            return 0
        n = 0
        for s in seeds:
            if not s.get("subject") or not s.get("statement"):
                continue
            self._store.put(Belief(
                subject=str(s["subject"]), statement=str(s["statement"]),
                domain=str(s.get("domain", "world")), confidence=float(s.get("confidence", 0.7)),
                valence=float(s.get("valence", 0.0)), source="innate"))
            n += 1
        return n

    # -- Algı / inanç oluşturma -------------------------------------------- #
    def observe(self, subject: str, statement: str, *, domain: str = "world",
                confidence: float = 0.6, valence: float = 0.0, source: str = "observation") -> Belief:
        """Yeni bir inanç ekler. Aynı konuda ZITTINI görürse mevcut inancı sessizce EZMEZ — çelişki
        olarak revizyona işaretler (çelişki 1. sınıf)."""
        belief = Belief(subject=subject, statement=statement, domain=domain,
                        confidence=confidence, valence=valence, source=source)
        for existing in self._store.list_by_subject(subject, status="active"):
            if existing.id == belief.id:
                continue
            if self._opposes(existing.valence, valence) and not existing.flagged_for_revision:
                existing.flagged_for_revision = True
                existing.revision_reason = f"yeni zıt kanıt: {statement[:60]}"
                existing.updated_at = now_iso()
                self._store.put(existing)
        self._store.put(belief)
        return belief

    def refute(self, belief_id: str, reason: str) -> Optional[Belief]:
        """Tahmin-hatası/kanıt bir inancı çürüttü → revizyon için işaretle (E3 Belief Revision'a düşer)."""
        b = self._store.get(belief_id)
        if b is None:
            return None
        b.flagged_for_revision = True
        b.revision_reason = reason
        b.updated_at = now_iso()
        self._store.put(b)
        return b

    @staticmethod
    def _opposes(v1: float, v2: float) -> bool:
        return v1 * v2 < 0 and abs(v1 - v2) >= _SIGNIFICANT_OPPOSITION

    def beliefs(self, domain: Optional[str] = None, status: str = "active") -> list[Belief]:
        return self._store.list(domain=domain, status=status)

    def get(self, belief_id: str) -> Optional[Belief]:
        return self._store.get(belief_id)

    def contradictions(self) -> list[Belief]:
        return self._store.list_flagged()

    # -- BeliefSource arayüzü (E3 Belief Revision) ------------------------- #
    def flagged_for_revision(self) -> list[dict[str, Any]]:
        return [{"id": b.id, "statement": b.statement, "reason": b.revision_reason}
                for b in self._store.list_flagged()]

    def mark_revised(self, belief_id: str, note: str = "") -> None:
        """E3, inancı revize ETTİĞİNİ bildirir: işaret temizlenir, güven düşürülür, statü 'revised'."""
        b = self._store.get(belief_id)
        if b is None:
            return
        b.flagged_for_revision = False
        b.status = "revised"
        b.confidence = round(max(0.0, b.confidence - 0.2), 3)
        if note:
            b.revision_reason = (b.revision_reason + " | revize: " + note).strip(" |")
        b.updated_at = now_iso()
        self._store.put(b)
