"""MIO Core · Federation Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

**Anayasa: egemenlik/gizlilik korunur; dış düğümle paylaşım ONAY ister (Madde 24) ve DETERMİNİSTİK scope sınırıyla
kısıtlanır.** Çekirdek: eş (peer) düğüm registry (endpoint/güven/yetenek) + **deterministik federasyon politikası**
(host allowlist + izinli paylaşım kapsamı) + güven durum makinesi (registered→trusted→revoked) + paylaşım job
durum makinesi. Gerçek uzak düğüm çağrısı enjekte edilen transport adapter'a (DI) delege; yoksa DÜRÜSTÇE
no_connector (uydurma sonuç YOK — Madde 8). Gerçek ağ/uzak yürütme çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PeerStatus:
    REGISTERED = "registered"   # kayıtlı ama güvenilmedi (paylaşım yapamaz)
    TRUSTED = "trusted"         # onaylı; scope sınırında paylaşım yapabilir
    REVOKED = "revoked"         # güven kaldırıldı — terminal
    ALL = {REGISTERED, TRUSTED, REVOKED}


PEER_TRANSITIONS = {
    PeerStatus.REGISTERED: {PeerStatus.TRUSTED, PeerStatus.REVOKED},
    PeerStatus.TRUSTED: {PeerStatus.REVOKED},
    PeerStatus.REVOKED: set(),
}


class TrustLevel:
    NONE = "none"
    BASIC = "basic"
    FULL = "full"
    ALL = {NONE, BASIC, FULL}


class ShareStatus:
    PENDING = "pending"
    REQUIRES_APPROVAL = "requires_approval"   # dış paylaşım onay bekliyor (Madde 24)
    SHARED = "shared"
    FAILED = "failed"
    NO_CONNECTOR = "no_connector"
    ALL = {PENDING, REQUIRES_APPROVAL, SHARED, FAILED, NO_CONNECTOR}


class FederationError(Exception):
    """Federation Domain temel hatası."""


class ValidationError(FederationError):
    pass


class UnauthorizedError(FederationError):
    pass


class NotFoundError(FederationError):
    pass


class TransitionError(FederationError):
    pass


@dataclass
class Peer:
    name: str
    endpoint: str = ""
    trust_level: str = TrustLevel.NONE
    capabilities: list = field(default_factory=list)
    status: str = PeerStatus.REGISTERED
    approved_by: str = ""
    rejected_reason: str = ""
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "endpoint": self.endpoint,
                "trust_level": self.trust_level, "capabilities": list(self.capabilities),
                "status": self.status, "approved_by": self.approved_by,
                "rejected_reason": self.rejected_reason, "description": self.description,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Peer":
        return cls(name=d["name"], endpoint=d.get("endpoint", ""),
                   trust_level=d.get("trust_level", TrustLevel.NONE),
                   capabilities=list(d.get("capabilities") or []),
                   status=d.get("status", PeerStatus.REGISTERED), approved_by=d.get("approved_by", ""),
                   rejected_reason=d.get("rejected_reason", ""), description=d.get("description", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   updated_at=d.get("updated_at") or _now())


@dataclass
class ShareJob:
    peer_id: str
    scope: str
    payload: dict = field(default_factory=dict)
    status: str = ShareStatus.PENDING
    result: dict = field(default_factory=dict)
    error: str = ""
    connector: str = ""
    approved_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "peer_id": self.peer_id, "scope": self.scope, "payload": self.payload,
                "status": self.status, "result": self.result, "error": self.error,
                "connector": self.connector, "approved_by": self.approved_by,
                "created_at": self.created_at, "finished_at": self.finished_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ShareJob":
        return cls(peer_id=d["peer_id"], scope=d["scope"], payload=dict(d.get("payload") or {}),
                   status=d.get("status", ShareStatus.PENDING), result=dict(d.get("result") or {}),
                   error=d.get("error", ""), connector=d.get("connector", ""),
                   approved_by=d.get("approved_by", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), finished_at=d.get("finished_at"))


@dataclass
class FederationConfig:
    # Güvenilir federasyon host'ları (allowlist — deterministik güven politikası)
    trusted_hosts: set = field(default_factory=set)
    # Egemenlik sınırı: yalnız bu kapsamlar dışarı paylaşılabilir
    allowed_scopes: set = field(default_factory=lambda: {
        "public_knowledge", "capability_catalog", "aggregate_metrics"})
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Planning", "Reasoning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering"})
    # Madde 24: dış düğümle güven/paylaşım yalnız bunlarca
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors

    def host_trusted(self, endpoint: str) -> bool:
        """Deterministik: peer endpoint host'u allowlist'te mi?"""
        if not endpoint:
            return False
        try:
            host = (urlparse(endpoint).hostname or "").lower()
        except Exception:  # noqa: BLE001 — bozuk endpoint güvenilmez
            return False
        return bool(host) and host in self.trusted_hosts

    def scope_allowed(self, scope: str) -> bool:
        return scope in self.allowed_scopes


__all__ = [
    "PeerStatus", "PEER_TRANSITIONS", "TrustLevel", "ShareStatus", "Peer", "ShareJob", "FederationConfig",
    "FederationError", "ValidationError", "UnauthorizedError", "NotFoundError", "TransitionError",
]
