"""MIO Core · E2 — Goal Management (uzun-vadeli hedef hiyerarşisi), LLM-BAĞIMSIZ çekirdek.

LongTermGoal → Milestone → GoalTask hiyerarşisi (30/90/365 gün ufku). MarkaAsistan `goal_manager`
deseninden UYARLANDI (kopya değil, stdlib, model-bağımsız). MIO'nun asıl amacı görev tamamlamak değil
uzun-vadeli hedefleri yönetmekse, E2 o hedeflerin omurgasıdır.

LLM-İLİŞKİSİ (ADR-0000 / çekirdek ilke): Hiyerarşi CRUD'u ve doğrulama DETERMİNİSTİKtir. LLM yalnız
`propose_milestones`'ta OPSİYONEL bir ÖNERİCİdir (adaptör); ufuk-dışı/geçersiz teklif DETERMİNİSTİK olarak
elenir — LLM karar vermez. Görev aktivasyonu (workflow üretimi) Execution'a (opsiyonel interpreter) devredilir.

E1-ENTEGRASYON: hedef oluşturulunca E1.track_goal; tamamlanınca/terk edilince E1 senkronlanır. E3 için
`GoalProgressSignals` (tamamlanan görev oranı = ilerleme) adaptörü sağlar.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from .models import new_id, now_iso

__all__ = [
    "LongTermGoal",
    "Milestone",
    "GoalTask",
    "GoalStore",
    "SQLiteGoalStore",
    "GoalManager",
    "GoalProgressSignals",
]


@dataclass
class LongTermGoal:
    text: str
    horizon_days: int
    id: str = field(default_factory=new_id)
    status: str = "active"                        # active | completed | abandoned
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "horizon_days": self.horizon_days,
                "status": self.status, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d): return cls(text=d["text"], horizon_days=int(d["horizon_days"]),
                                      id=d.get("id") or new_id(), status=d.get("status", "active"),
                                      created_at=d.get("created_at") or now_iso())


@dataclass
class Milestone:
    goal_id: str
    title: str
    target_day_offset: int
    id: str = field(default_factory=new_id)
    status: str = "pending"                       # pending | in_progress | completed | failed
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "goal_id": self.goal_id, "title": self.title,
                "target_day_offset": self.target_day_offset, "status": self.status,
                "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d): return cls(goal_id=d["goal_id"], title=d["title"],
                                      target_day_offset=int(d["target_day_offset"]),
                                      id=d.get("id") or new_id(), status=d.get("status", "pending"),
                                      created_at=d.get("created_at") or now_iso())


@dataclass
class GoalTask:
    goal_id: str
    milestone_id: str
    description: str
    id: str = field(default_factory=new_id)
    status: str = "pending"                       # pending | activated | running | completed | failed
    result_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "goal_id": self.goal_id, "milestone_id": self.milestone_id,
                "description": self.description, "status": self.status,
                "result_summary": self.result_summary, "created_at": self.created_at,
                "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d): return cls(goal_id=d["goal_id"], milestone_id=d["milestone_id"],
                                      description=d["description"], id=d.get("id") or new_id(),
                                      status=d.get("status", "pending"),
                                      result_summary=dict(d.get("result_summary") or {}),
                                      created_at=d.get("created_at") or now_iso(),
                                      updated_at=d.get("updated_at") or now_iso())


@runtime_checkable
class GoalStore(Protocol):
    def put_goal(self, goal: LongTermGoal) -> None: ...
    def get_goal(self, goal_id: str) -> Optional[LongTermGoal]: ...
    def list_goals(self, status: Optional[str] = None) -> list[LongTermGoal]: ...
    def put_milestone(self, m: Milestone) -> None: ...
    def get_milestone(self, milestone_id: str) -> Optional[Milestone]: ...
    def list_milestones(self, goal_id: str) -> list[Milestone]: ...
    def put_task(self, t: GoalTask) -> None: ...
    def get_task(self, task_id: str) -> Optional[GoalTask]: ...
    def list_tasks(self, goal_id: Optional[str] = None,
                   milestone_id: Optional[str] = None) -> list[GoalTask]: ...
    def close(self) -> None: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS milestones (id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ms_goal ON milestones(goal_id);
CREATE TABLE IF NOT EXISTS goal_tasks (
    id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, milestone_id TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_gt_goal ON goal_tasks(goal_id);
CREATE INDEX IF NOT EXISTS ix_gt_ms ON goal_tasks(milestone_id);
"""


class SQLiteGoalStore:
    """Üretim-kalite SQLite hedef deposu (E1/E5 deseniyle aynı)."""

    def __init__(self, path: str = "mio_goals.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def _put(self, table: str, id_: str, cols: dict, data: dict) -> None:
        keys = ["id"] + list(cols) + ["data"]
        vals = [id_] + list(cols.values()) + [json.dumps(data, ensure_ascii=False)]
        setters = ", ".join(f"{k}=excluded.{k}" for k in keys if k != "id")
        with self._lock:
            self._conn.execute(
                f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))}) "
                f"ON CONFLICT(id) DO UPDATE SET {setters}", vals)
            self._conn.commit()

    def put_goal(self, goal): self._put("goals", goal.id, {"status": goal.status}, goal.to_dict())

    def get_goal(self, goal_id):
        r = self._conn.execute("SELECT data FROM goals WHERE id=?", (goal_id,)).fetchone()
        return LongTermGoal.from_dict(json.loads(r["data"])) if r else None

    def list_goals(self, status=None):
        if status:
            rows = self._conn.execute("SELECT data FROM goals WHERE status=? ORDER BY rowid", (status,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM goals ORDER BY rowid").fetchall()
        return [LongTermGoal.from_dict(json.loads(r["data"])) for r in rows]

    def put_milestone(self, m): self._put("milestones", m.id, {"goal_id": m.goal_id}, m.to_dict())

    def get_milestone(self, milestone_id):
        r = self._conn.execute("SELECT data FROM milestones WHERE id=?", (milestone_id,)).fetchone()
        return Milestone.from_dict(json.loads(r["data"])) if r else None

    def list_milestones(self, goal_id):
        rows = self._conn.execute(
            "SELECT data FROM milestones WHERE goal_id=? ORDER BY rowid", (goal_id,)).fetchall()
        return [Milestone.from_dict(json.loads(r["data"])) for r in rows]

    def put_task(self, t):
        self._put("goal_tasks", t.id, {"goal_id": t.goal_id, "milestone_id": t.milestone_id}, t.to_dict())

    def get_task(self, task_id):
        r = self._conn.execute("SELECT data FROM goal_tasks WHERE id=?", (task_id,)).fetchone()
        return GoalTask.from_dict(json.loads(r["data"])) if r else None

    def list_tasks(self, goal_id=None, milestone_id=None):
        if milestone_id:
            rows = self._conn.execute(
                "SELECT data FROM goal_tasks WHERE milestone_id=? ORDER BY rowid", (milestone_id,)).fetchall()
        elif goal_id:
            rows = self._conn.execute(
                "SELECT data FROM goal_tasks WHERE goal_id=? ORDER BY rowid", (goal_id,)).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM goal_tasks ORDER BY rowid").fetchall()
        return [GoalTask.from_dict(json.loads(r["data"])) for r in rows]

    def close(self):
        with self._lock:
            self._conn.close()


# Opsiyonel LLM önerici: (goal_text, horizon_days) -> [{"title","target_day_offset"}]  (danışman)
MilestoneProposer = Callable[[str, int], list[dict[str, Any]]]
# Opsiyonel Execution interpreter: (task) -> workflow_id | None
TaskInterpreter = Callable[[GoalTask], Optional[str]]


class GoalManager:
    """E2 hedef yöneticisi. Deterministik çekirdek; LLM/Execution opsiyonel adaptör. E1'e senkron."""

    def __init__(self, store: GoalStore, *, executive_state=None) -> None:
        self._store = store
        self._state = executive_state           # E1 ExecutiveState (opsiyonel) — aktif hedef indeksi

    def create_goal(self, text: str, horizon_days: int) -> LongTermGoal:
        if not (1 <= horizon_days <= 730):
            raise ValueError("horizon_days 1..730 aralığında olmalı")
        goal = LongTermGoal(text=text, horizon_days=horizon_days)
        self._store.put_goal(goal)
        if self._state is not None:
            self._state.track_goal(goal.id, status="active", horizon_days=horizon_days)
        return goal

    def add_milestone(self, goal_id: str, title: str, target_day_offset: int) -> Milestone:
        goal = self._require_goal(goal_id)
        if not (0 < target_day_offset <= goal.horizon_days):
            raise ValueError(f"Milestone ufuk dışı: {target_day_offset} (ufuk {goal.horizon_days})")
        m = Milestone(goal_id=goal_id, title=title, target_day_offset=target_day_offset)
        self._store.put_milestone(m)
        return m

    def propose_milestones(self, goal_id: str, proposer: Optional[MilestoneProposer] = None) -> list[Milestone]:
        """LLM (opsiyonel danışman) milestone ÖNERİR; ufuk-dışı/geçersiz teklif DETERMİNİSTİK elenir.
        proposer yoksa boş liste (dürüst — uydurma milestone yok)."""
        if proposer is None:
            return []
        goal = self._require_goal(goal_id)
        try:
            raw = proposer(goal.text, goal.horizon_days) or []
        except Exception:
            raw = []
        added: list[Milestone] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()[:200]
            offset = item.get("target_day_offset")
            if not title or not isinstance(offset, (int, float)) or not (0 < offset <= goal.horizon_days):
                continue                          # ufuk-dışı/geçersiz → sessizce elenir
            m = Milestone(goal_id=goal_id, title=title, target_day_offset=int(offset))
            self._store.put_milestone(m)
            added.append(m)
        return added

    def add_task(self, goal_id: str, milestone_id: str, description: str) -> GoalTask:
        self._require_goal(goal_id)
        if self._store.get_milestone(milestone_id) is None:
            raise ValueError(f"Milestone bulunamadı: {milestone_id}")
        t = GoalTask(goal_id=goal_id, milestone_id=milestone_id, description=description)
        self._store.put_task(t)
        return t

    def activate_task(self, task_id: str, interpreter: Optional[TaskInterpreter] = None) -> GoalTask:
        """Görevi Execution'a hazırlar. interpreter (opsiyonel) GERÇEK bir workflow üretir; yoksa
        'activated' işaretlenir (sahte workflow_id UYDURULMAZ)."""
        t = self._require_task(task_id)
        if interpreter is not None:
            wf = interpreter(t)
            if wf:
                t.result_summary["workflow_id"] = wf
                t.status = "running"
            else:
                t.status = "activated"            # yorumlayıcı üretemedi → dürüstçe hazır ama workflowsuz
        else:
            t.status = "activated"
        t.updated_at = now_iso()
        self._store.put_task(t)
        return t

    def record_task_result(self, task_id: str, status: str,
                           result_summary: Optional[dict[str, Any]] = None) -> GoalTask:
        """Gerçek yürütme sonucunu geri yazar (Execution/Feedback) + deterministik ilerleme:
        milestone'ın tüm görevleri bittiyse milestone tamamlanır; tüm milestone'lar bittiyse hedef tamamlanır."""
        t = self._require_task(task_id)
        t.status = status
        if result_summary:
            t.result_summary = {**t.result_summary, **result_summary}
        t.updated_at = now_iso()
        self._store.put_task(t)
        self._advance(t.milestone_id, t.goal_id)
        return t

    def abandon_goal(self, goal_id: str) -> LongTermGoal:
        goal = self._require_goal(goal_id)
        goal.status = "abandoned"
        self._store.put_goal(goal)
        if self._state is not None:
            self._state.untrack_goal(goal_id)     # aktif indeksten düş (Madde 12: meşru vazgeçiş)
        return goal

    def goal_tree(self, goal_id: str) -> dict[str, Any]:
        goal = self._require_goal(goal_id)
        milestones = self._store.list_milestones(goal_id)
        tasks = self._store.list_tasks(goal_id=goal_id)
        by_ms: dict[str, list[dict]] = {}
        for t in tasks:
            by_ms.setdefault(t.milestone_id, []).append(t.to_dict())
        return {"goal": goal.to_dict(),
                "milestones": [{**m.to_dict(), "tasks": by_ms.get(m.id, [])} for m in milestones]}

    def progress(self, goal_id: str) -> float:
        """Tamamlanan görev oranı [0,1] (E3 GoalSignals'ı besler). Görev yoksa 0.0."""
        tasks = self._store.list_tasks(goal_id=goal_id)
        if not tasks:
            return 0.0
        done = sum(1 for t in tasks if t.status == "completed")
        return round(done / len(tasks), 3)

    # -- iç yardımcılar ----------------------------------------------------- #
    def _advance(self, milestone_id: str, goal_id: str) -> None:
        ms_tasks = self._store.list_tasks(milestone_id=milestone_id)
        m = self._store.get_milestone(milestone_id)
        if m is not None and ms_tasks and all(t.status == "completed" for t in ms_tasks):
            if m.status != "completed":
                m.status = "completed"
                self._store.put_milestone(m)
        milestones = self._store.list_milestones(goal_id)
        goal = self._store.get_goal(goal_id)
        if goal is not None and milestones and all(x.status == "completed" for x in milestones):
            if goal.status != "completed":
                goal.status = "completed"
                self._store.put_goal(goal)
                if self._state is not None:
                    self._state.track_goal(goal_id, status="completed", horizon_days=goal.horizon_days)

    def _require_goal(self, goal_id: str) -> LongTermGoal:
        g = self._store.get_goal(goal_id)
        if g is None:
            raise ValueError(f"Hedef bulunamadı: {goal_id}")
        return g

    def _require_task(self, task_id: str) -> GoalTask:
        t = self._store.get_task(task_id)
        if t is None:
            raise ValueError(f"Görev bulunamadı: {task_id}")
        return t


class GoalProgressSignals:
    """E3 GoalSignals adaptörü — E2'den GERÇEK ilerleme; meaningful/risk bilinmiyor (None, dürüst)."""

    def __init__(self, manager: GoalManager) -> None:
        self._m = manager

    def meaningful(self, goal_id: str) -> Optional[bool]:
        return None

    def progress(self, goal_id: str) -> Optional[float]:
        try:
            return self._m.progress(goal_id)
        except ValueError:
            return None

    def risk(self, goal_id: str) -> Optional[float]:
        return None
