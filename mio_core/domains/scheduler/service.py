"""MIO Core · Scheduler/Lifecycle Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Otonom döngü motoru. `tick()` mantıksal saati 1 ilerletir ve vadesi gelen işleri KAYIT SIRASINA göre
deterministik çalıştırır. **Duvar-saati thread YOK** — çökme/kontrolsüz süreç riski yoktur; gerçek-zaman
sürücüsü kenarda opsiyonel adaptördür. LoopGuard (ardışık-hata devre kesici + tick başına yürütme tavanı) ve
zombie-guard (çökmüş süreçten kalan 'running' koşuları toparlama) çalışma-zamanı sağlamlığını sağlar."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, SchedEvents, scheduler_contract
from .models import (
    Job,
    LifecycleState,
    NotFoundError,
    RunStatus,
    ScheduleRun,
    SchedulerConfig,
    UnauthorizedError,
    ValidationError,
)
from .repository import ScheduleRepository

logger = logging.getLogger("mio.domain.scheduler")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SchedulerDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: ScheduleRepository, *, bus=None,
                 config: Optional[SchedulerConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or SchedulerConfig()
        self._jobs: dict[str, Job] = {}
        self._clock = 0
        self._state = LifecycleState.RUNNING
        self._metrics = {"ticks": 0, "job_runs": 0, "disabled": 0, "reaped": 0}

    # ------------------------------------------------------------------ #
    def register_job(self, actor: str, name: str, handler: Callable[[], Any], *, interval: int = 1,
                     one_shot: bool = False, max_failures: int = 3,
                     run_at: Optional[int] = None) -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "iş adı")
        if name in self._jobs:
            raise ValidationError(f"İş zaten kayıtlı: {name}")
        if not callable(handler):
            raise ValidationError("handler çağrılabilir olmalı")
        if interval < 1:
            raise ValidationError("interval >= 1 olmalı")
        next_due = run_at if run_at is not None else self._clock + interval
        self._jobs[name] = Job(name=name, handler=handler, interval=interval, next_due=next_due,
                               one_shot=one_shot, max_failures=max_failures)
        self._emit(SchedEvents.JOB_REGISTERED, {"actor": actor, "job": name, "interval": interval})
        return self._jobs[name].to_dict()

    def tick(self, actor: str) -> dict[str, Any]:
        """Mantıksal saati 1 ilerletir; vadesi gelen işleri deterministik çalıştırır (LoopGuard'lı)."""
        self._authorize_writer(actor)
        if self._state != LifecycleState.RUNNING:
            return {"clock": self._clock, "state": self._state, "ran": [], "note": "çalışmıyor"}
        self._clock += 1
        self._metrics["ticks"] += 1
        ran, disabled, executions = [], [], 0
        for job in list(self._jobs.values()):                # kayıt sırası = deterministik
            if not job.enabled or job.next_due > self._clock:
                continue
            if executions >= self._cfg.max_runs_per_tick:     # LoopGuard tavanı
                logger.warning("Scheduler: tick tavanı aşıldı (%d)", self._cfg.max_runs_per_tick)
                break
            run = self._execute(job)
            executions += 1
            ran.append({"job": job.name, "status": run.status})
            self._post_run(job, run, disabled)
        self._emit(SchedEvents.TICK, {"clock": self._clock, "ran": len(ran), "disabled": disabled})
        return {"clock": self._clock, "state": self._state, "ran": ran, "disabled": disabled,
                "executions": executions}

    def run_now(self, actor: str, name: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        job = self._jobs.get(name)
        if job is None:
            raise NotFoundError(f"İş bulunamadı: {name}")
        run = self._execute(job)
        self._post_run(job, run, [])
        return run.to_dict()

    # -- yaşam-döngüsü ----------------------------------------------------- #
    def start(self, actor: str) -> dict[str, Any]:
        return self._transition(actor, LifecycleState.RUNNING)

    def pause(self, actor: str) -> dict[str, Any]:
        return self._transition(actor, LifecycleState.PAUSED)

    def resume(self, actor: str) -> dict[str, Any]:
        return self._transition(actor, LifecycleState.RUNNING)

    def stop(self, actor: str) -> dict[str, Any]:
        return self._transition(actor, LifecycleState.STOPPED)

    def enable_job(self, actor: str, name: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        job = self._require_job(name)
        job.enabled = True
        job.failures = 0                                     # devreyi sıfırla
        return job.to_dict()

    def disable_job(self, actor: str, name: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        job = self._require_job(name)
        job.enabled = False
        return job.to_dict()

    # -- zombie-guard ------------------------------------------------------ #
    def reap_zombies(self, actor: str) -> dict[str, Any]:
        """Çökmüş önceki süreçten kalan 'running' koşuları toparlar (başlangıçta çağrılır)."""
        self._authorize_writer(actor)
        zombies = self._repo.list_by_status(RunStatus.RUNNING)
        for r in zombies:
            r.status = RunStatus.REAPED
            r.finished_at = _now()
            r.error = (r.error + " | zombie-guard: önceki süreçten toparlandı").strip(" |")
            self._repo.put(r)
        if zombies:
            self._metrics["reaped"] += len(zombies)
            self._emit(SchedEvents.ZOMBIE_REAPED, {"count": len(zombies)})
            logger.info("Scheduler: %d zombie koşu toparlandı", len(zombies))
        return {"reaped": len(zombies)}

    # -- sorgu ------------------------------------------------------------- #
    def jobs(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [j.to_dict() for j in self._jobs.values()]

    def run_history(self, actor: str, *, limit: Optional[int] = None,
                    job: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        n = min(int(limit or self._cfg.history_limit), self._cfg.history_limit)
        return [r.to_dict() for r in self._repo.recent(n, job=job)]

    def explain(self, actor: str, run_id: str) -> dict[str, Any]:
        self._authorize(actor)
        run = self._repo.get(run_id)
        if run is None:
            raise NotFoundError(f"Koşu bulunamadı: {run_id}")
        return run.to_dict()

    def stats(self) -> dict[str, Any]:
        return {"clock": self._clock, "state": self._state, "jobs": len(self._jobs),
                "enabled_jobs": sum(1 for j in self._jobs.values() if j.enabled),
                "runs": self._repo.count(), "completed": self._repo.count(status=RunStatus.COMPLETED),
                "failed": self._repo.count(status=RunStatus.FAILED), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return scheduler_contract()

    # ------------------------------------------------------------------ #
    def _execute(self, job: Job) -> ScheduleRun:
        run = ScheduleRun(job=job.name, tick=self._clock, status=RunStatus.RUNNING)
        self._repo.put(run)                                  # ÖNCE 'running' yazılır (zombie-guard için)
        try:
            out = job.handler()
            run.status = RunStatus.COMPLETED
            run.output = ("" if out is None else str(out))[: self._cfg.output_limit]
        except Exception as exc:  # noqa: BLE001 — iş hatası motoru durdurmaz (izole + devre kesici)
            run.status = RunStatus.FAILED
            run.error = str(exc)[: self._cfg.output_limit]
            logger.warning("Scheduler: iş '%s' başarısız: %s", job.name, exc)
        run.finished_at = _now()
        self._repo.put(run)
        job.runs += 1
        job.last_status = run.status
        self._metrics["job_runs"] += 1
        self._emit(SchedEvents.JOB_RAN, {"job": job.name, "status": run.status, "run_id": run.id})
        return run

    def _post_run(self, job: Job, run: ScheduleRun, disabled: list) -> None:
        if job.one_shot:
            job.enabled = False
        else:
            job.next_due = self._clock + job.interval
        if run.status == RunStatus.FAILED:
            job.failures += 1
            if job.failures >= job.max_failures:             # LoopGuard: devre aç
                job.enabled = False
                disabled.append(job.name)
                self._metrics["disabled"] += 1
                self._emit(SchedEvents.JOB_DISABLED, {"job": job.name, "failures": job.failures})
        else:
            job.failures = 0                                 # başarı → devreyi kapat

    def _transition(self, actor: str, state: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        prev, self._state = self._state, state
        self._emit(SchedEvents.LIFECYCLE, {"actor": actor, "from": prev, "to": state})
        return {"state": self._state, "previous": prev}

    def _require_job(self, name: str) -> Job:
        job = self._jobs.get(name)
        if job is None:
            raise NotFoundError(f"İş bulunamadı: {name}")
        return job

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' zamanlayıcı erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' zamanlayıcı yönetimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
