"""MIO Core · Scheduler/Lifecycle Domain — modeller, hatalar, config (production-grade), LLM-BAĞIMSIZ.

Otonom döngü motoru: DETERMİNİSTİK mantıksal tick'ler (duvar-saati thread YOK — çökme/kontrolsüz süreç riski
yok; gerçek-zaman sürücüsü kenarda opsiyonel adaptör). LoopGuard (ardışık-hata devre kesici + tick başına
yürütme tavanı) ve zombie-guard (çökmüş koşuları toparlama) çalışma-zamanı sağlamlığını sağlar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LifecycleState:
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ALL = {RUNNING, PAUSED, STOPPED}


class RunStatus:
    RUNNING = "running"       # başladı, henüz bitmedi (çökme olursa zombie adayı)
    COMPLETED = "completed"
    FAILED = "failed"
    REAPED = "reaped"         # zombie-guard tarafından toparlandı (önceki çökmüş süreç)
    ALL = {RUNNING, COMPLETED, FAILED, REAPED}


class SchedulerError(Exception):
    """Scheduler Domain temel hatası."""


class ValidationError(SchedulerError):
    pass


class UnauthorizedError(SchedulerError):
    pass


class NotFoundError(SchedulerError):
    pass


@dataclass
class Job:
    """Kayıtlı iş (handler serileştirilmez — her boot'ta yeniden bağlanır, klasik scheduler deseni)."""
    name: str
    handler: Callable[[], Any]
    interval: int = 1                    # her N tick'te bir
    next_due: int = 0                    # bu tick'te/öncesinde ise çalışır
    enabled: bool = True
    one_shot: bool = False
    max_failures: int = 3               # ardışık bu kadar hata → devre açılır (disabled)
    failures: int = 0
    runs: int = 0
    last_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "interval": self.interval, "next_due": self.next_due,
                "enabled": self.enabled, "one_shot": self.one_shot, "max_failures": self.max_failures,
                "failures": self.failures, "runs": self.runs, "last_status": self.last_status}


@dataclass
class ScheduleRun:
    job: str
    tick: int
    status: str = RunStatus.RUNNING
    output: str = ""
    error: str = ""
    started_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None
    id: str = field(default_factory=lambda: uuid4().hex[:16])

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "job": self.job, "tick": self.tick, "status": self.status,
                "output": self.output, "error": self.error, "started_at": self.started_at,
                "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScheduleRun":
        return cls(job=d["job"], tick=int(d.get("tick", 0)), status=d.get("status", RunStatus.RUNNING),
                   output=d.get("output", ""), error=d.get("error", ""),
                   started_at=d.get("started_at") or _now(), finished_at=d.get("finished_at"),
                   id=d.get("id") or uuid4().hex[:16])


@dataclass
class SchedulerConfig:
    max_runs_per_tick: int = 100         # LoopGuard tavanı (kontrolsüz iş-tetikler-iş patlamasını önler)
    output_limit: int = 500              # koşu çıktısı bu kadar karaktere kırpılır
    history_limit: int = 200
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Workflow"})
    writer_actors: set = field(default_factory=lambda: {"owner", "Executive", "Operations", "Workflow"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "LifecycleState", "RunStatus", "Job", "ScheduleRun", "SchedulerConfig",
    "SchedulerError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
