"""MIO Core · Scheduler/Lifecycle Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class SchedEvents:
    TICK = "scheduler.tick"
    JOB_RAN = "scheduler.job_ran"
    JOB_DISABLED = "scheduler.job_disabled"       # LoopGuard: ardışık hata → devre açıldı
    JOB_REGISTERED = "scheduler.job_registered"
    LIFECYCLE = "scheduler.lifecycle"             # start/pause/resume/stop
    ZOMBIE_REAPED = "scheduler.zombie_reaped"


OPERATIONS = ("register_job", "tick", "run_now", "start", "pause", "resume", "stop",
              "enable_job", "disable_job", "reap_zombies", "jobs", "run_history", "stats")


def scheduler_contract() -> dict[str, Any]:
    return {
        "domain": "scheduler",
        "version": CONTRACT_VERSION,
        "description": "Otonom döngü motoru: DETERMİNİSTİK mantıksal tick'ler + LoopGuard (devre kesici + "
                       "tick tavanı) + zombie-guard + yaşam-döngüsü. Duvar-saati thread yok (çökme riski yok).",
        "operations": list(OPERATIONS),
        "events": [SchedEvents.TICK, SchedEvents.JOB_RAN, SchedEvents.JOB_DISABLED,
                   SchedEvents.JOB_REGISTERED, SchedEvents.LIFECYCLE, SchedEvents.ZOMBIE_REAPED],
        "lifecycle_states": ["running", "paused", "stopped"],
        "invariants": ["tick deterministiktir (mantıksal saat, duvar-saati değil)",
                       "LoopGuard: ardışık hata devreyi açar; tick başına yürütme tavanı vardır",
                       "zombie-guard: çökmüş süreçten kalan 'running' koşular toparlanır",
                       "durdurulmuş/duraklatılmış durumda iş çalışmaz"],
    }
