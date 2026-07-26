"""MIO Core · Marketplace / Ecosystem Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

**Anayasa: denetlenmemiş üçüncü-taraf yetenek platforma SOKULAMAZ.** Çekirdek: yayın (listing) registry
(yetenek/eklenti/model/veri/MCP) + yayıncı/sürüm/imza + **deterministik uyumluluk & allowlist politikası** +
inceleme/kurulum durum makinesi (submitted→approved/rejected→installed/removed). **Kurulum ONAY ister** (Madde 24;
yalnız owner/Executive onaylar; uyumlu/güvenilir değilse otomatik reddedilir). Gerçek indirme/kurulum enjekte
edilen kaynak adapter'a (DI) delege; yoksa DÜRÜSTÇE no_connector (uydurma sonuç YOK — Madde 8). Gerçek kurulum/
çalıştırma çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ListingKind:
    CAPABILITY = "capability"
    PLUGIN = "plugin"
    MODEL = "model"
    DATASET = "dataset"
    MCP_SERVER = "mcp_server"
    ALL = {CAPABILITY, PLUGIN, MODEL, DATASET, MCP_SERVER}


class ListingStatus:
    SUBMITTED = "submitted"     # inceleme bekliyor (onay = Madde 24 kapısı)
    APPROVED = "approved"       # uyumlu + güvenilir + onaylı; kurulabilir
    REJECTED = "rejected"       # uyumsuz/denetimsiz — terminal
    INSTALLED = "installed"     # kaynak adapter ile kuruldu
    REMOVED = "removed"         # kaldırıldı — terminal
    ALL = {SUBMITTED, APPROVED, REJECTED, INSTALLED, REMOVED}


# Deterministik yaşam-döngüsü geçişleri (izinli hedefler)
TRANSITIONS = {
    ListingStatus.SUBMITTED: {ListingStatus.APPROVED, ListingStatus.REJECTED},
    ListingStatus.APPROVED: {ListingStatus.INSTALLED, ListingStatus.REMOVED, ListingStatus.REJECTED},
    ListingStatus.INSTALLED: {ListingStatus.REMOVED},
    ListingStatus.REJECTED: set(),
    ListingStatus.REMOVED: set(),
}


class MarketplaceError(Exception):
    """Marketplace Domain temel hatası."""


class ValidationError(MarketplaceError):
    pass


class UnauthorizedError(MarketplaceError):
    pass


class NotFoundError(MarketplaceError):
    pass


class TransitionError(MarketplaceError):
    pass


@dataclass
class Listing:
    name: str
    kind: str = ListingKind.CAPABILITY
    publisher: str = ""
    version: str = "1.0.0"
    source_uri: str = ""
    signature: str = ""
    description: str = ""
    status: str = ListingStatus.SUBMITTED
    compatible: bool = False
    compat_reasons: list = field(default_factory=list)
    install_ref: str = ""
    connector: str = ""
    approved_by: str = ""
    rejected_reason: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "publisher": self.publisher,
                "version": self.version, "source_uri": self.source_uri, "signature": self.signature,
                "description": self.description, "status": self.status, "compatible": self.compatible,
                "compat_reasons": list(self.compat_reasons), "install_ref": self.install_ref,
                "connector": self.connector, "approved_by": self.approved_by,
                "rejected_reason": self.rejected_reason, "created_at": self.created_at,
                "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Listing":
        return cls(name=d["name"], kind=d.get("kind", ListingKind.CAPABILITY),
                   publisher=d.get("publisher", ""), version=d.get("version", "1.0.0"),
                   source_uri=d.get("source_uri", ""), signature=d.get("signature", ""),
                   description=d.get("description", ""), status=d.get("status", ListingStatus.SUBMITTED),
                   compatible=bool(d.get("compatible", False)),
                   compat_reasons=list(d.get("compat_reasons") or []), install_ref=d.get("install_ref", ""),
                   connector=d.get("connector", ""), approved_by=d.get("approved_by", ""),
                   rejected_reason=d.get("rejected_reason", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now())


@dataclass
class MarketplaceConfig:
    # Güvenilir yayıncılar ve kaynak host'ları (allowlist — deterministik uyumluluk politikası)
    trusted_publishers: set = field(default_factory=lambda: {"mio", "first-party"})
    trusted_sources: set = field(default_factory=lambda: {"registry.mio.local"})
    require_signature: bool = True
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Reasoning", "Planning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering"})
    # Madde 24: üçüncü-taraf yeteneği yalnız bunlar onaylayabilir
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors

    def evaluate(self, listing: "Listing") -> tuple[bool, list]:
        """DETERMİNİSTİK uyumluluk & allowlist politikası. (compatible, reasons)."""
        reasons: list = []
        host = ""
        if listing.source_uri:
            try:
                host = (urlparse(listing.source_uri).hostname or "").lower()
            except Exception:  # noqa: BLE001 — bozuk uri güvenilmez sayılır
                host = ""
        publisher_ok = listing.publisher in self.trusted_publishers
        source_ok = host in self.trusted_sources if host else False
        if not (publisher_ok or source_ok):
            reasons.append("untrusted_source")     # ne yayıncı ne kaynak allowlist'te
        if self.require_signature and not listing.signature.strip():
            reasons.append("unsigned")
        if listing.kind not in ListingKind.ALL:
            reasons.append("invalid_kind")
        return (len(reasons) == 0, reasons)


__all__ = [
    "ListingKind", "ListingStatus", "TRANSITIONS", "Listing", "MarketplaceConfig",
    "MarketplaceError", "ValidationError", "UnauthorizedError", "NotFoundError", "TransitionError",
]
