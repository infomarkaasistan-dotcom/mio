"""MIO Core · IoT Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

IoT erişimi GERÇEK broker/protokol (MQTT/CoAP/HTTP/Zigbee) + fiziksel cihaz gerektirir → çekirdek deterministik
ORKESTRASYON: thing (sensör/aktüatör/gateway) registry + **telemetri alım + eşik-tabanlı uyarı** (deterministik)
+ aktüatör **komut job durum makinesi** + connector routing + risk sınıflandırma. Aktüatör aksiyonları
geri-alınamaz olabilir (vana/kilit/röle) → **yüksek-risk komut ONAY ister** (Madde 24). Gerçek protokol/cihaz
erişimi enjekte edilen connector'a (adapter) delege; connector yoksa DÜRÜSTÇE no_connector (uydurma sonuç YOK —
Madde 8). Protokol/donanım erişimi çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ThingKind:
    SENSOR = "sensor"            # telemetri üretir (okuma alınır, komut KABUL ETMEZ)
    ACTUATOR = "actuator"        # komut uygular (vana/kilit/röle — geri-alınamaz olabilir)
    GATEWAY = "gateway"          # köprü (hem telemetri hem komut)
    ALL = {SENSOR, ACTUATOR, GATEWAY}
    COMMANDABLE = {ACTUATOR, GATEWAY}   # komut kabul edenler


class Protocol:
    MQTT = "mqtt"
    COAP = "coap"
    HTTP = "http"
    ZIGBEE = "zigbee"
    ALL = {MQTT, COAP, HTTP, ZIGBEE}


class Risk:
    LOW = "low"
    HIGH = "high"               # geri-alınamaz/tehlikeli aktüatör aksiyonu → onay şart


class OpStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_CONNECTOR = "no_connector"
    REQUIRES_APPROVAL = "requires_approval"   # yüksek-risk, onay bekliyor (Madde 24)
    ALL = {PENDING, RUNNING, COMPLETED, FAILED, NO_CONNECTOR, REQUIRES_APPROVAL}


# Deterministik yüksek-risk aktüatör komut işaretleri (geri-alınamaz/fiziksel/tehlikeli)
HIGH_RISK_MARKERS = ("unlock", "open", "disable", "override", "shutdown", "reboot", "reset", "wipe",
                     "factory", "erase", "kilit", "aç", "kapat", "sıfırla", "sil", "devre dışı")

# Eşik karşılaştırıcıları (deterministik)
COMPARATORS = {
    ">": lambda v, t: v > t,
    ">=": lambda v, t: v >= t,
    "<": lambda v, t: v < t,
    "<=": lambda v, t: v <= t,
    "==": lambda v, t: v == t,
    "!=": lambda v, t: v != t,
}


class IoTError(Exception):
    """IoT Domain temel hatası."""


class ValidationError(IoTError):
    pass


class UnauthorizedError(IoTError):
    pass


class NotFoundError(IoTError):
    pass


def classify_risk(command: str, declared: str = Risk.LOW) -> str:
    """Deterministik risk: bildirilen 'high' ise ya da komut tehlikeli işaret içeriyorsa → high."""
    cmd = (command or "").lower()
    if declared == Risk.HIGH or any(m in cmd for m in HIGH_RISK_MARKERS):
        return Risk.HIGH
    return Risk.LOW


@dataclass
class Thing:
    name: str
    kind: str = ThingKind.SENSOR
    protocol: str = Protocol.MQTT
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "protocol": self.protocol,
                "description": self.description, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Thing":
        return cls(name=d["name"], kind=d.get("kind", ThingKind.SENSOR),
                   protocol=d.get("protocol", Protocol.MQTT), description=d.get("description", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now())


@dataclass
class Reading:
    thing_id: str
    metric: str
    value: float
    unit: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "thing_id": self.thing_id, "metric": self.metric, "value": self.value,
                "unit": self.unit, "ts": self.ts}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Reading":
        return cls(thing_id=d["thing_id"], metric=d["metric"], value=float(d["value"]),
                   unit=d.get("unit", ""), id=d.get("id") or uuid4().hex[:12], ts=d.get("ts") or _now())


@dataclass
class AlertRule:
    thing_id: str
    metric: str
    comparator: str
    threshold: float
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "thing_id": self.thing_id, "metric": self.metric,
                "comparator": self.comparator, "threshold": self.threshold, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AlertRule":
        return cls(thing_id=d["thing_id"], metric=d["metric"], comparator=d["comparator"],
                   threshold=float(d["threshold"]), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class Alert:
    rule_id: str
    thing_id: str
    metric: str
    value: float
    comparator: str
    threshold: float
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "rule_id": self.rule_id, "thing_id": self.thing_id, "metric": self.metric,
                "value": self.value, "comparator": self.comparator, "threshold": self.threshold, "ts": self.ts}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Alert":
        return cls(rule_id=d["rule_id"], thing_id=d["thing_id"], metric=d["metric"], value=float(d["value"]),
                   comparator=d["comparator"], threshold=float(d["threshold"]),
                   id=d.get("id") or uuid4().hex[:12], ts=d.get("ts") or _now())


@dataclass
class CommandJob:
    thing_id: str
    command: str
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
        return {"id": self.id, "thing_id": self.thing_id, "command": self.command, "params": self.params,
                "risk": self.risk, "status": self.status, "result": self.result, "error": self.error,
                "connector": self.connector, "approved_by": self.approved_by, "created_at": self.created_at,
                "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CommandJob":
        return cls(thing_id=d["thing_id"], command=d["command"], params=dict(d.get("params") or {}),
                   risk=d.get("risk", Risk.LOW), status=d.get("status", OpStatus.PENDING),
                   result=dict(d.get("result") or {}), error=d.get("error", ""),
                   connector=d.get("connector", ""), approved_by=d.get("approved_by", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   finished_at=d.get("finished_at"))


@dataclass
class IoTConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Perception", "Reasoning", "Planning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering"})
    # Madde 24: yüksek-risk aktüatör komutunu yalnız bunlar onaylayabilir
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "ThingKind", "Protocol", "Risk", "OpStatus", "HIGH_RISK_MARKERS", "COMPARATORS", "classify_risk",
    "Thing", "Reading", "AlertRule", "Alert", "CommandJob", "IoTConfig",
    "IoTError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
