"""MIO Core · Simulation & Digital Twin Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

**Anayasa: SİMÜLASYON ≠ GERÇEKLİK; sonuç ÖNERİDİR, yansıtma Madde 24 onayı ister.** Twin registry + **deterministik
durum/geçiş simülasyonu** (state + adım/effect; what-if) + senaryo çalıştırma kaydı. `simulate()` ikizi MUTATE
ETMEZ (kopya üstünde). Dış fiziksel model gerekli ikiz için enjekte edilen simülatör adapter'a (DI) delege; yoksa
**no_simulator** (uydurma sonuç YOK — Madde 8). Gerçek varlık kontrolü çekirdekte YOK. authz · validation · events ·
observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, DigitalTwinEvents, digital_twin_contract
from .models import (
    DigitalTwinConfig,
    NotFoundError,
    SimStatus,
    SimulationRun,
    Twin,
    UnauthorizedError,
    ValidationError,
    apply_step,
)
from .repository import DigitalTwinRepository

logger = logging.getLogger("mio.domain.digital_twin")

Simulator = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DigitalTwinDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: DigitalTwinRepository, *, bus=None,
                 config: Optional[DigitalTwinConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or DigitalTwinConfig()
        self._simulators: dict[str, tuple[Simulator, str]] = {}   # twin kind -> (fn, adapter adı)
        self._metrics = {"twins": 0, "simulations": 0, "no_simulator": 0, "failed": 0, "applied": 0}

    # ------------------------------------------------------------------ #
    def register_simulator(self, kind: str, fn: Simulator, *, name: str = "adapter") -> None:
        """Bir ikiz türü için GERÇEK/dış fiziksel simülatör connector'ı bağlar (kompozisyon-zamanı DI)."""
        kind = self._require(kind, "tür")
        self._simulators[kind] = (fn, name)

    def register_twin(self, actor: str, name: str, *, kind: str = "generic",
                      state: Optional[dict] = None, requires_external_sim: bool = False,
                      description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "ikiz adı")
        t = Twin(name=name, kind=kind, state=dict(state or {}),
                 requires_external_sim=bool(requires_external_sim), description=description)
        self._repo.put_twin(t)
        self._metrics["twins"] += 1
        self._emit(DigitalTwinEvents.TWIN_REGISTERED, {"actor": actor, "id": t.id, "kind": kind})
        return t.to_dict()

    def update_state(self, actor: str, twin_id: str, state: dict) -> dict[str, Any]:
        """İkizin GERÇEK gözlemlenen durumunu günceller (telemetri senkron; simülasyon değil)."""
        self._authorize_writer(actor)
        t = self._require_twin(twin_id)
        if not isinstance(state, dict):
            raise ValidationError("state bir sözlük olmalı")
        t.state.update(state)
        t.updated_at = _now()
        self._repo.put_twin(t)
        return t.to_dict()

    def simulate(self, actor: str, twin_id: str, steps: list, *, scenario: str = "") -> dict[str, Any]:
        """DETERMİNİSTİK what-if: adımları ikizin durum KOPYASINA uygular. İkizi MUTATE ETMEZ (sim ≠ gerçeklik)."""
        self._authorize_writer(actor)
        t = self._require_twin(twin_id)
        if not isinstance(steps, list):
            raise ValidationError("steps bir liste olmalı")
        run = SimulationRun(twin_id=twin_id, scenario=scenario, initial_state=dict(t.state))
        self._metrics["simulations"] += 1

        # Dış fiziksel model gerekli ama adapter yok → DÜRÜST no_simulator
        if t.requires_external_sim and t.kind not in self._simulators:
            run.status = SimStatus.NO_SIMULATOR
            self._repo.put_run(run)
            self._metrics["no_simulator"] += 1
            self._emit(DigitalTwinEvents.NO_SIMULATOR, {"id": run.id, "twin_id": twin_id, "kind": t.kind})
            return run.to_dict()

        try:
            entry = self._simulators.get(t.kind)
            if entry is not None:                # dış simülatöre delege (yine deterministik beklenir)
                fn, sname = entry
                result = fn({"twin": t.to_dict(), "steps": list(steps), "scenario": scenario}) or {}
                run.final_state = dict(result.get("final_state", t.state))
                run.trace = list(result.get("trace", []))
                run.simulator = sname
            else:                                # dahili deterministik simülatör (gerçek hesap, placeholder DEĞİL)
                state = dict(t.state)
                trace: list = []
                for step in steps:
                    state, entry_trace = apply_step(state, step)
                    trace.append(entry_trace)
                run.final_state = state
                run.trace = trace
                run.simulator = "internal"
            run.status = SimStatus.COMPLETED
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 — simülatör hatası çalıştırmaya dönüşür, sistemi bozmaz
            run.status = SimStatus.FAILED
            run.error = str(exc)[:300]
            self._metrics["failed"] += 1
            self._repo.put_run(run)
            self._emit(DigitalTwinEvents.SIM_FAILED, {"id": run.id, "error": run.error})
            return run.to_dict()

        self._repo.put_run(run)
        # NOT: ikiz DEĞİŞMEDİ — sim ≠ gerçeklik. Yansıtmak için apply_result (Madde 24).
        self._emit(DigitalTwinEvents.SIMULATED, {"id": run.id, "twin_id": twin_id, "steps": len(steps)})
        return run.to_dict()

    def apply_result(self, actor: str, run_id: str) -> dict[str, Any]:
        """Simülasyon sonucunu ikiz modeline yansıtır (yalnız approver — Madde 24; sim ≠ gerçeklik sınırı)."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' simülasyon sonucunu yansıtamaz (Madde 24)")
        run = self._repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Simülasyon bulunamadı: {run_id}")
        if run.status != SimStatus.COMPLETED:
            raise ValidationError(f"Yalnız 'completed' simülasyon yansıtılır (durum: {run.status})")
        if run.applied:
            raise ValidationError("Simülasyon sonucu zaten yansıtıldı")
        t = self._require_twin(run.twin_id)
        t.state = dict(run.final_state)          # ikiz modeline commit (gerçek varlık DEĞİL — o çekirdek dışı)
        t.updated_at = _now()
        self._repo.put_twin(t)
        run.applied = True
        run.applied_by = actor
        self._repo.put_run(run)
        self._metrics["applied"] += 1
        self._emit(DigitalTwinEvents.RESULT_APPLIED, {"id": run_id, "twin_id": t.id, "by": actor})
        return {"applied": True, "twin": t.to_dict(), "run": run.to_dict()}

    # -- sorgular -------------------------------------------------------- #
    def get_twin(self, actor: str, twin_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_twin(twin_id).to_dict()

    def list_twins(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [t.to_dict() for t in self._repo.all_twins()]

    def get_run(self, actor: str, run_id: str) -> dict[str, Any]:
        self._authorize(actor)
        r = self._repo.get_run(run_id)
        if r is None:
            raise NotFoundError(f"Simülasyon bulunamadı: {run_id}")
        return r.to_dict()

    def list_runs(self, actor: str, *, twin_id: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if twin_id is not None:
            self._require_twin(twin_id)
            return [r.to_dict() for r in self._repo.runs_for(twin_id)]
        return [r.to_dict() for r in self._repo.all_runs()]

    def simulators(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"registered_kinds": sorted(self._simulators)}

    def stats(self) -> dict[str, Any]:
        return {"twins": self._repo.twin_count(), "runs": self._repo.run_count(),
                "simulators": len(self._simulators), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return digital_twin_contract()

    # ------------------------------------------------------------------ #
    def _require_twin(self, twin_id: str) -> Twin:
        t = self._repo.get_twin(twin_id)
        if t is None:
            raise NotFoundError(f"İkiz bulunamadı: {twin_id}")
        return t

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' dijital ikiz erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' ikiz/simülasyon için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
