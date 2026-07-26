"""MIO Core · IoT Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Thing registry + telemetri alım + **eşik-tabanlı uyarı (deterministik)** + aktüatör komut durum makinesi +
connector routing (protokole göre) + risk sınıflandırma. **Yüksek-risk/geri-alınamaz aktüatör komut ONAY ister**
(Madde 24); onaysız çalışmaz. Sensör komut kabul etmez. Gerçek protokol/cihaz enjekte edilen connector'a (adapter)
delege; **connector yoksa no_connector** (uydurma sonuç YOK — Madde 8). Protokol/donanım erişimi çekirdekte YOK.
authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, IoTEvents, iot_contract
from .models import (
    Alert,
    AlertRule,
    CommandJob,
    COMPARATORS,
    IoTConfig,
    NotFoundError,
    OpStatus,
    Protocol,
    Reading,
    Risk,
    Thing,
    ThingKind,
    UnauthorizedError,
    ValidationError,
    classify_risk,
)
from .repository import IoTRepository

logger = logging.getLogger("mio.domain.iot")

Connector = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IoTDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: IoTRepository, *, bus=None,
                 config: Optional[IoTConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or IoTConfig()
        self._connectors: dict[str, tuple[Connector, str]] = {}   # protocol -> (fn, name)
        self._metrics = {"things": 0, "readings": 0, "alerts": 0, "commands": 0, "completed": 0,
                         "no_connector": 0, "failed": 0, "approval_required": 0}

    # ------------------------------------------------------------------ #
    def register_connector(self, protocol: str, fn: Connector, *, name: str = "adapter") -> None:
        """Bir protokol için GERÇEK broker/cihaz connector'ı bağlar (kompozisyon-zamanı DI)."""
        if protocol not in Protocol.ALL:
            raise ValidationError(f"Geçersiz protokol: {protocol}")
        self._connectors[protocol] = (fn, name)

    def register_thing(self, actor: str, name: str, *, kind: str = ThingKind.SENSOR,
                       protocol: str = Protocol.MQTT, description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "thing adı")
        if kind not in ThingKind.ALL:
            raise ValidationError(f"Geçersiz thing türü: {kind}")
        if protocol not in Protocol.ALL:
            raise ValidationError(f"Geçersiz protokol: {protocol}")
        t = Thing(name=name, kind=kind, protocol=protocol, description=description)
        self._repo.put_thing(t)
        self._metrics["things"] += 1
        self._emit(IoTEvents.THING_REGISTERED, {"actor": actor, "id": t.id, "kind": kind, "protocol": protocol})
        return t.to_dict()

    # -- telemetri ------------------------------------------------------- #
    def ingest(self, actor: str, thing_id: str, metric: str, value: float, *,
               unit: str = "") -> dict[str, Any]:
        """Telemetri okuması kaydeder ve deterministik eşik kurallarını değerlendirir (tetiklenirse alarm)."""
        self._authorize_writer(actor)
        self._require_thing(thing_id)
        metric = self._require(metric, "metrik")
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"Sayısal değer bekleniyor: {value!r}")
        reading = Reading(thing_id=thing_id, metric=metric, value=val, unit=unit)
        self._repo.put_reading(reading)
        self._metrics["readings"] += 1
        self._emit(IoTEvents.TELEMETRY_INGESTED, {"thing_id": thing_id, "metric": metric, "value": val})
        triggered = self._evaluate_rules(thing_id, metric, val)
        return {"reading": reading.to_dict(), "alerts": triggered}

    def add_alert_rule(self, actor: str, thing_id: str, metric: str, comparator: str,
                       threshold: float) -> dict[str, Any]:
        """Deterministik eşik kuralı ekler: value <comparator> threshold → alarm."""
        self._authorize_writer(actor)
        self._require_thing(thing_id)
        metric = self._require(metric, "metrik")
        if comparator not in COMPARATORS:
            raise ValidationError(f"Geçersiz karşılaştırıcı: {comparator}")
        try:
            thr = float(threshold)
        except (TypeError, ValueError):
            raise ValidationError(f"Sayısal eşik bekleniyor: {threshold!r}")
        rule = AlertRule(thing_id=thing_id, metric=metric, comparator=comparator, threshold=thr)
        self._repo.put_rule(rule)
        self._emit(IoTEvents.ALERT_RULE_ADDED, {"id": rule.id, "thing_id": thing_id, "metric": metric})
        return rule.to_dict()

    def _evaluate_rules(self, thing_id: str, metric: str, value: float) -> list[dict[str, Any]]:
        fired: list[dict[str, Any]] = []
        for rule in self._repo.rules_for(thing_id, metric):
            if COMPARATORS[rule.comparator](value, rule.threshold):
                alert = Alert(rule_id=rule.id, thing_id=thing_id, metric=metric, value=value,
                              comparator=rule.comparator, threshold=rule.threshold)
                self._repo.put_alert(alert)
                self._metrics["alerts"] += 1
                self._emit(IoTEvents.ALERT_TRIGGERED, {"id": alert.id, "thing_id": thing_id,
                           "metric": metric, "value": value, "threshold": rule.threshold})
                fired.append(alert.to_dict())
        return fired

    # -- aktüatör komutları (Madde 24) ---------------------------------- #
    def send_command(self, actor: str, thing_id: str, command: str, *, params: Optional[dict] = None,
                     risk: str = Risk.LOW, user_approved: bool = False) -> dict[str, Any]:
        """Aktüatör komutu oluşturur. Sensör komut kabul etmez. Yüksek-risk + onaysız → requires_approval."""
        self._authorize_writer(actor)
        thing = self._require_thing(thing_id)
        command = self._require(command, "komut")
        if thing.kind not in ThingKind.COMMANDABLE:
            raise ValidationError(f"'{thing.kind}' komut kabul etmez (yalnız actuator/gateway)")
        eff_risk = classify_risk(command, risk)
        job = CommandJob(thing_id=thing_id, command=command, params=dict(params or {}),
                         risk=eff_risk, status=OpStatus.PENDING)
        self._metrics["commands"] += 1
        self._emit(IoTEvents.COMMAND_CREATED, {"id": job.id, "risk": eff_risk})

        if eff_risk == Risk.HIGH and not user_approved:      # Madde 24: onaysız çalışmaz
            job.status = OpStatus.REQUIRES_APPROVAL
            self._repo.put_command(job)
            self._metrics["approval_required"] += 1
            self._emit(IoTEvents.APPROVAL_REQUIRED, {"id": job.id, "command": command})
            return job.to_dict()
        return self._dispatch(job, thing)

    def approve_command(self, actor: str, job_id: str) -> dict[str, Any]:
        """Onay bekleyen yüksek-risk komutu onaylar ve çalıştırır (yalnız approver — Madde 24)."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' yüksek-risk komut onaylayamaz (Madde 24)")
        job = self._repo.get_command(job_id)
        if job is None:
            raise NotFoundError(f"Komut bulunamadı: {job_id}")
        if job.status != OpStatus.REQUIRES_APPROVAL:
            raise ValidationError(f"Yalnız 'requires_approval' onaylanır (durum: {job.status})")
        job.approved_by = actor
        thing = self._require_thing(job.thing_id)
        self._emit(IoTEvents.APPROVED, {"id": job_id, "by": actor})
        return self._dispatch(job, thing)

    def _dispatch(self, job: CommandJob, thing: Thing) -> dict[str, Any]:
        entry = self._connectors.get(thing.protocol)
        if entry is None:                       # DÜRÜST: gerçek protokol connector'ı bağlı değil
            job.status = OpStatus.NO_CONNECTOR
            job.finished_at = _now()
            self._repo.put_command(job)
            self._metrics["no_connector"] += 1
            self._emit(IoTEvents.NO_CONNECTOR, {"id": job.id, "protocol": thing.protocol})
            return job.to_dict()
        fn, name = entry
        job.connector = name
        job.status = OpStatus.RUNNING
        try:
            result = fn({"thing": thing.to_dict(), "command": job.command, "params": job.params})
            job.status = OpStatus.COMPLETED
            job.result = dict(result or {})
            self._metrics["completed"] += 1
            self._emit(IoTEvents.COMMAND_COMPLETED, {"id": job.id, "connector": name})
        except Exception as exc:  # noqa: BLE001 — connector hatası işe dönüşür, sistemi bozmaz
            job.status = OpStatus.FAILED
            job.error = str(exc)[:300]
            self._metrics["failed"] += 1
            self._emit(IoTEvents.COMMAND_FAILED, {"id": job.id, "error": job.error})
        job.finished_at = _now()
        self._repo.put_command(job)
        return job.to_dict()

    # -- sorgular -------------------------------------------------------- #
    def readings(self, actor: str, thing_id: str, *, metric: Optional[str] = None,
                 limit: int = 100) -> list[dict[str, Any]]:
        self._authorize(actor)
        self._require_thing(thing_id)
        return [r.to_dict() for r in self._repo.readings(thing_id, metric=metric, limit=limit)]

    def latest(self, actor: str, thing_id: str, metric: str) -> Optional[dict[str, Any]]:
        self._authorize(actor)
        self._require_thing(thing_id)
        r = self._repo.latest_reading(thing_id, metric)
        return r.to_dict() if r else None

    def alerts(self, actor: str, *, thing_id: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [a.to_dict() for a in self._repo.all_alerts(thing_id=thing_id)]

    def get_command(self, actor: str, job_id: str) -> dict[str, Any]:
        self._authorize(actor)
        j = self._repo.get_command(job_id)
        if j is None:
            raise NotFoundError(f"Komut bulunamadı: {job_id}")
        return j.to_dict()

    def list_commands(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in OpStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [j.to_dict() for j in self._repo.all_commands(status=status)]

    def list_things(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [t.to_dict() for t in self._repo.all_things()]

    def connectors(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"available": sorted(self._connectors), "all_protocols": sorted(Protocol.ALL),
                "missing": sorted(Protocol.ALL - set(self._connectors))}

    def stats(self) -> dict[str, Any]:
        return {"things": self._repo.thing_count(), "readings": self._repo.reading_count(),
                "rules": self._repo.rule_count(), "alerts_recorded": self._repo.alert_count(),
                "commands": self._repo.command_count(),
                "pending_approval": self._repo.command_count(status=OpStatus.REQUIRES_APPROVAL),
                "connectors": len(self._connectors), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return iot_contract()

    # ------------------------------------------------------------------ #
    def _require_thing(self, thing_id: str) -> Thing:
        t = self._repo.get_thing(thing_id)
        if t is None:
            raise NotFoundError(f"Thing bulunamadı: {thing_id}")
        return t

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' IoT erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' IoT yazma/komut için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
