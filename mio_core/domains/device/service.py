"""MIO Core · Device & Native Integration Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Device registry + komut durum makinesi + connector routing + risk sınıflandırma. **Yüksek-risk/geri-alınamaz
komut ONAY ister** (Madde 24); onaysız çalışmaz. Gerçek OS/donanım enjekte edilen handler'a (adapter) delege;
**handler yoksa no_connector** (uydurma sonuç YOK — Madde 8). Donanım erişimi çekirdekte YOK. authz · validation ·
events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, DeviceEvents, device_contract
from .models import (
    CommandJob,
    Device,
    DeviceConfig,
    DeviceKind,
    NotFoundError,
    OpStatus,
    Risk,
    UnauthorizedError,
    ValidationError,
    classify_risk,
)
from .repository import DeviceRepository

logger = logging.getLogger("mio.domain.device")

Handler = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeviceNativeDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: DeviceRepository, *, bus=None,
                 config: Optional[DeviceConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or DeviceConfig()
        self._handlers: dict[str, tuple[Handler, str]] = {}
        self._metrics = {"devices": 0, "commands": 0, "completed": 0, "no_connector": 0,
                         "failed": 0, "approval_required": 0}

    # ------------------------------------------------------------------ #
    def register_handler(self, device_kind: str, fn: Handler, *, name: str = "adapter") -> None:
        """Bir aygıt türü için GERÇEK erişim connector'ı bağlar (kompozisyon-zamanı DI)."""
        if device_kind not in DeviceKind.ALL:
            raise ValidationError(f"Geçersiz aygıt türü: {device_kind}")
        self._handlers[device_kind] = (fn, name)

    def register_device(self, actor: str, name: str, *, kind: str = DeviceKind.OS,
                        description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "aygıt adı")
        if kind not in DeviceKind.ALL:
            raise ValidationError(f"Geçersiz aygıt türü: {kind}")
        dev = Device(name=name, kind=kind, description=description)
        self._repo.put_device(dev)
        self._metrics["devices"] += 1
        self._emit(DeviceEvents.DEVICE_REGISTERED, {"actor": actor, "id": dev.id, "kind": kind})
        return dev.to_dict()

    def execute(self, actor: str, device_id: str, operation: str, *, params: Optional[dict] = None,
                risk: str = Risk.LOW, user_approved: bool = False) -> dict[str, Any]:
        """Komut işi oluşturur. Yüksek-risk + onaysız → requires_approval (Madde 24); aksi → delege."""
        self._authorize_writer(actor)
        device = self._require_device(device_id)
        operation = self._require(operation, "operasyon")
        eff_risk = classify_risk(operation, risk)
        job = CommandJob(device_id=device_id, operation=operation, params=dict(params or {}),
                         risk=eff_risk, status=OpStatus.PENDING)
        self._metrics["commands"] += 1
        self._emit(DeviceEvents.COMMAND_CREATED, {"id": job.id, "risk": eff_risk})

        if eff_risk == Risk.HIGH and not user_approved:      # Madde 24: onaysız çalışmaz
            job.status = OpStatus.REQUIRES_APPROVAL
            self._repo.put_job(job)
            self._metrics["approval_required"] += 1
            self._emit(DeviceEvents.APPROVAL_REQUIRED, {"id": job.id, "operation": operation})
            return job.to_dict()
        return self._dispatch(job, device)

    def approve_command(self, actor: str, job_id: str) -> dict[str, Any]:
        """Onay bekleyen yüksek-risk komutu onaylar ve çalıştırır (yalnız approver — Madde 24)."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' yüksek-risk komut onaylayamaz (Madde 24)")
        job = self._repo.get_job(job_id)
        if job is None:
            raise NotFoundError(f"Komut bulunamadı: {job_id}")
        if job.status != OpStatus.REQUIRES_APPROVAL:
            raise ValidationError(f"Yalnız 'requires_approval' onaylanır (durum: {job.status})")
        job.approved_by = actor
        device = self._require_device(job.device_id)
        self._emit(DeviceEvents.APPROVED, {"id": job_id, "by": actor})
        return self._dispatch(job, device)

    # ------------------------------------------------------------------ #
    def _dispatch(self, job: CommandJob, device: Device) -> dict[str, Any]:
        entry = self._handlers.get(device.kind)
        if entry is None:                       # DÜRÜST: gerçek erişim connector'ı bağlı değil
            job.status = OpStatus.NO_CONNECTOR
            job.finished_at = _now()
            self._repo.put_job(job)
            self._metrics["no_connector"] += 1
            self._emit(DeviceEvents.NO_CONNECTOR, {"id": job.id, "kind": device.kind})
            return job.to_dict()
        fn, name = entry
        job.connector = name
        job.status = OpStatus.RUNNING
        try:
            result = fn({"device": device.to_dict(), "operation": job.operation, "params": job.params})
            job.status = OpStatus.COMPLETED
            job.result = dict(result or {})
            self._metrics["completed"] += 1
            self._emit(DeviceEvents.COMMAND_COMPLETED, {"id": job.id, "connector": name})
        except Exception as exc:  # noqa: BLE001 — connector hatası işe dönüşür, sistemi bozmaz
            job.status = OpStatus.FAILED
            job.error = str(exc)[:300]
            self._metrics["failed"] += 1
            self._emit(DeviceEvents.COMMAND_FAILED, {"id": job.id, "error": job.error})
        job.finished_at = _now()
        self._repo.put_job(job)
        return job.to_dict()

    # ------------------------------------------------------------------ #
    def get_job(self, actor: str, job_id: str) -> dict[str, Any]:
        self._authorize(actor)
        j = self._repo.get_job(job_id)
        if j is None:
            raise NotFoundError(f"Komut bulunamadı: {job_id}")
        return j.to_dict()

    def list_jobs(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in OpStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [j.to_dict() for j in self._repo.all_jobs(status=status)]

    def list_devices(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [d.to_dict() for d in self._repo.all_devices()]

    def connectors(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"available": sorted(self._handlers), "all_kinds": sorted(DeviceKind.ALL),
                "missing": sorted(DeviceKind.ALL - set(self._handlers))}

    def stats(self) -> dict[str, Any]:
        return {"devices": self._repo.device_count(), "commands": self._repo.job_count(),
                "pending_approval": self._repo.job_count(status=OpStatus.REQUIRES_APPROVAL),
                "connectors": len(self._handlers), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return device_contract()

    # ------------------------------------------------------------------ #
    def _require_device(self, device_id: str) -> Device:
        d = self._repo.get_device(device_id)
        if d is None:
            raise NotFoundError(f"Aygıt bulunamadı: {device_id}")
        return d

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' aygıt erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' aygıt komutu için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
