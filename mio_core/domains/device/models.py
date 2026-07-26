"""MIO Core · Device & Native Integration Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Native/donanım erişimi GERÇEK OS/aygıt gerektirir → çekirdek deterministik ORKESTRASYON: device registry +
komut job durum makinesi + connector routing + risk sınıflandırma (yüksek-risk/geri-alınamaz komut ONAY ister,
Madde 24). Gerçek erişim enjekte edilen handler'a (adapter) delege; handler yoksa DÜRÜSTÇE no_connector (uydurma
sonuç YOK — Madde 8). Donanım/OS erişimi çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeviceKind:
    OS = "os"                # işletim sistemi komutları
    FILESYSTEM = "filesystem"
    PERIPHERAL = "peripheral"   # yazıcı/kamera/mikrofon vb.
    ALL = {OS, FILESYSTEM, PERIPHERAL}


class Risk:
    LOW = "low"
    HIGH = "high"            # geri-alınamaz/tehlikeli → onay şart


class OpStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_CONNECTOR = "no_connector"
    REQUIRES_APPROVAL = "requires_approval"   # yüksek-risk, onay bekliyor (Madde 24)
    ALL = {PENDING, RUNNING, COMPLETED, FAILED, NO_CONNECTOR, REQUIRES_APPROVAL}


# Deterministik yüksek-risk operasyon işaretleri (geri-alınamaz/tehlikeli)
HIGH_RISK_MARKERS = ("delete", "format", "shutdown", "reboot", "wipe", "erase", "rm ", "kill",
                     "sil", "biçimlendir", "kapat")


class DeviceError(Exception):
    """Device Domain temel hatası."""


class ValidationError(DeviceError):
    pass


class UnauthorizedError(DeviceError):
    pass


class NotFoundError(DeviceError):
    pass


def classify_risk(operation: str, declared: str = Risk.LOW) -> str:
    """Deterministik risk: bildirilen 'high' ise ya da operasyon tehlikeli işaret içeriyorsa → high."""
    op = (operation or "").lower()
    if declared == Risk.HIGH or any(m in op for m in HIGH_RISK_MARKERS):
        return Risk.HIGH
    return Risk.LOW


@dataclass
class Device:
    name: str
    kind: str = DeviceKind.OS
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "description": self.description,
                "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Device":
        return cls(name=d["name"], kind=d.get("kind", DeviceKind.OS), description=d.get("description", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now())


@dataclass
class CommandJob:
    device_id: str
    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    risk: str = Risk.LOW
    status: str = OpStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    connector: str = ""
    approved_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "device_id": self.device_id, "operation": self.operation,
                "params": self.params, "risk": self.risk, "status": self.status, "result": self.result,
                "error": self.error, "connector": self.connector, "approved_by": self.approved_by,
                "created_at": self.created_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CommandJob":
        return cls(device_id=d["device_id"], operation=d["operation"], params=dict(d.get("params") or {}),
                   risk=d.get("risk", Risk.LOW), status=d.get("status", OpStatus.PENDING),
                   result=dict(d.get("result") or {}), error=d.get("error", ""),
                   connector=d.get("connector", ""), approved_by=d.get("approved_by", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   finished_at=d.get("finished_at"))


@dataclass
class DeviceConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Perception", "Reasoning", "Planning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering"})
    # Madde 24: yüksek-risk komutu yalnız bunlar onaylayabilir
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "DeviceKind", "Risk", "OpStatus", "HIGH_RISK_MARKERS", "classify_risk", "Device", "CommandJob",
    "DeviceConfig",
    "DeviceError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
