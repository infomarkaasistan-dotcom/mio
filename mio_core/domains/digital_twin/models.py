"""MIO Core · Simulation & Digital Twin Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

**Anayasa: SİMÜLASYON ≠ GERÇEKLİK; simülasyon sonucu ÖNERİDİR, ikiz modeline/gerçeğe otomatik uygulanmaz; yansıtma
Madde 24 onayı ister.** Çekirdek: dijital ikiz (twin) registry (gerçek varlığın durum modeli) + **deterministik
durum/geçiş simülasyonu** (state + kural-tabanlı adım/effect; what-if, LLM'siz) + senaryo çalıştırma kaydı. Gerçek
fiziksel model gerektiren ikiz için dış simülatör adapter'a (DI) delege; yoksa DÜRÜSTÇE no_simulator (uydurma sonuç
YOK — Madde 8). **simulate() ikizi MUTATE ETMEZ** (kopya üstünde çalışır). Gerçek varlık kontrolü çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Deterministik adım operasyonları (state değişkenleri üzerinde)
STEP_OPS = {"set", "inc", "dec", "mul", "min", "max"}

NUMERIC_OPS = {"inc", "dec", "mul", "min", "max"}


class SimStatus:
    COMPLETED = "completed"
    NO_SIMULATOR = "no_simulator"   # dış simülatör gerekli ama bağlı değil (dürüst)
    FAILED = "failed"
    ALL = {COMPLETED, NO_SIMULATOR, FAILED}


class DigitalTwinError(Exception):
    """Digital Twin Domain temel hatası."""


class ValidationError(DigitalTwinError):
    pass


class UnauthorizedError(DigitalTwinError):
    pass


class NotFoundError(DigitalTwinError):
    pass


def apply_step(state: dict, step: dict) -> tuple[dict, dict]:
    """Deterministik olarak tek adımı uygular. (yeni_state, trace_kaydı) döner. Girdi state MUTATE EDİLMEZ."""
    op = step.get("op")
    var = str(step.get("var", "")).strip()
    if op not in STEP_OPS:
        raise ValidationError(f"Geçersiz adım operasyonu: {op}")
    if not var:
        raise ValidationError("Adım 'var' boş olamaz")
    new_state = dict(state)
    before = new_state.get(var)
    value = step.get("value")
    if op == "set":
        new_state[var] = value
    else:                                    # sayısal operasyonlar
        try:
            cur = float(before if before is not None else 0.0)
            num = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"'{op}' sayısal değer gerektirir (var={var})")
        if op == "inc":
            new_state[var] = cur + num
        elif op == "dec":
            new_state[var] = cur - num
        elif op == "mul":
            new_state[var] = cur * num
        elif op == "min":
            new_state[var] = min(cur, num)
        elif op == "max":
            new_state[var] = max(cur, num)
    return new_state, {"op": op, "var": var, "before": before, "after": new_state[var]}


@dataclass
class Twin:
    name: str
    kind: str = "generic"
    state: dict = field(default_factory=dict)
    requires_external_sim: bool = False     # gerçek fiziksel model gerekiyorsa True (dış adapter şart)
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "state": dict(self.state),
                "requires_external_sim": self.requires_external_sim, "description": self.description,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Twin":
        return cls(name=d["name"], kind=d.get("kind", "generic"), state=dict(d.get("state") or {}),
                   requires_external_sim=bool(d.get("requires_external_sim", False)),
                   description=d.get("description", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now())


@dataclass
class SimulationRun:
    twin_id: str
    scenario: str
    initial_state: dict = field(default_factory=dict)
    final_state: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)
    status: str = SimStatus.COMPLETED
    error: str = ""
    simulator: str = "internal"
    applied: bool = False                   # sonuç gerçeğe/ikize yansıtıldı mı (Madde 24 sonrası)
    applied_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "twin_id": self.twin_id, "scenario": self.scenario,
                "initial_state": dict(self.initial_state), "final_state": dict(self.final_state),
                "trace": list(self.trace), "status": self.status, "error": self.error,
                "simulator": self.simulator, "applied": self.applied, "applied_by": self.applied_by,
                "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SimulationRun":
        return cls(twin_id=d["twin_id"], scenario=d.get("scenario", ""),
                   initial_state=dict(d.get("initial_state") or {}),
                   final_state=dict(d.get("final_state") or {}), trace=list(d.get("trace") or []),
                   status=d.get("status", SimStatus.COMPLETED), error=d.get("error", ""),
                   simulator=d.get("simulator", "internal"), applied=bool(d.get("applied", False)),
                   applied_by=d.get("applied_by", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class DigitalTwinConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Planning", "Reasoning", "Perception"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Planning"})
    # Madde 24: simülasyon sonucunu ikize/gerçeğe yansıtmayı yalnız bunlar onaylar
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "STEP_OPS", "NUMERIC_OPS", "SimStatus", "apply_step", "Twin", "SimulationRun", "DigitalTwinConfig",
    "DigitalTwinError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
