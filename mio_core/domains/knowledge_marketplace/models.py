"""MIO Core · Knowledge Marketplace Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

**Anayasa: denetlenmemiş bilgi Knowledge Domain'e/çekirdeğe SOKULAMAZ.** Çekirdek: bilgi paketi (knowledge pack)
registry (fact-set/ontology/prompt-lib/skill) + yayıncı/sürüm/lisans/checksum + **deterministik kalite & lisans &
allowlist politikası** + import durum makinesi (submitted→approved/rejected→imported/removed) + **provenance
(kaynak izlenebilirlik) etiketi**. **Import ONAY ister** (Madde 24; yalnız owner/Executive; uyumsuz/lisanssız
otomatik reddedilir). Gerçek indirme/import enjekte edilen kaynak adapter'a (DI) delege; yoksa DÜRÜSTÇE
no_connector (uydurma sonuç YOK — Madde 8). Gerçek indirme/çalıştırma çekirdekte YOK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PackKind:
    FACT_SET = "fact_set"
    ONTOLOGY = "ontology"
    PROMPT_LIB = "prompt_lib"
    SKILL = "skill"
    ALL = {FACT_SET, ONTOLOGY, PROMPT_LIB, SKILL}


class PackStatus:
    SUBMITTED = "submitted"     # inceleme bekliyor (onay = Madde 24 kapısı)
    APPROVED = "approved"       # uyumlu + lisanslı + onaylı; import edilebilir
    REJECTED = "rejected"       # uyumsuz/lisanssız/denetimsiz — terminal
    IMPORTED = "imported"       # kaynak adapter ile Knowledge Domain'e aktarıldı
    REMOVED = "removed"         # kaldırıldı — terminal
    ALL = {SUBMITTED, APPROVED, REJECTED, IMPORTED, REMOVED}


TRANSITIONS = {
    PackStatus.SUBMITTED: {PackStatus.APPROVED, PackStatus.REJECTED},
    PackStatus.APPROVED: {PackStatus.IMPORTED, PackStatus.REMOVED, PackStatus.REJECTED},
    PackStatus.IMPORTED: {PackStatus.REMOVED},
    PackStatus.REJECTED: set(),
    PackStatus.REMOVED: set(),
}


class KnowledgeMarketError(Exception):
    """Knowledge Marketplace Domain temel hatası."""


class ValidationError(KnowledgeMarketError):
    pass


class UnauthorizedError(KnowledgeMarketError):
    pass


class NotFoundError(KnowledgeMarketError):
    pass


class TransitionError(KnowledgeMarketError):
    pass


@dataclass
class KnowledgePack:
    name: str
    kind: str = PackKind.FACT_SET
    publisher: str = ""
    version: str = "1.0.0"
    license: str = ""
    source_uri: str = ""
    checksum: str = ""
    item_count: int = 0
    description: str = ""
    status: str = PackStatus.SUBMITTED
    compatible: bool = False
    compat_reasons: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    imported_ref: str = ""
    imported_items: int = 0
    connector: str = ""
    approved_by: str = ""
    rejected_reason: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "publisher": self.publisher,
                "version": self.version, "license": self.license, "source_uri": self.source_uri,
                "checksum": self.checksum, "item_count": self.item_count, "description": self.description,
                "status": self.status, "compatible": self.compatible,
                "compat_reasons": list(self.compat_reasons), "provenance": dict(self.provenance),
                "imported_ref": self.imported_ref, "imported_items": self.imported_items,
                "connector": self.connector, "approved_by": self.approved_by,
                "rejected_reason": self.rejected_reason, "created_at": self.created_at,
                "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "KnowledgePack":
        return cls(name=d["name"], kind=d.get("kind", PackKind.FACT_SET), publisher=d.get("publisher", ""),
                   version=d.get("version", "1.0.0"), license=d.get("license", ""),
                   source_uri=d.get("source_uri", ""), checksum=d.get("checksum", ""),
                   item_count=int(d.get("item_count", 0)), description=d.get("description", ""),
                   status=d.get("status", PackStatus.SUBMITTED), compatible=bool(d.get("compatible", False)),
                   compat_reasons=list(d.get("compat_reasons") or []),
                   provenance=dict(d.get("provenance") or {}), imported_ref=d.get("imported_ref", ""),
                   imported_items=int(d.get("imported_items", 0)), connector=d.get("connector", ""),
                   approved_by=d.get("approved_by", ""), rejected_reason=d.get("rejected_reason", ""),
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   updated_at=d.get("updated_at") or _now())


@dataclass
class KnowledgeMarketConfig:
    trusted_publishers: set = field(default_factory=lambda: {"mio", "first-party"})
    trusted_sources: set = field(default_factory=lambda: {"registry.mio.local"})
    allowed_licenses: set = field(default_factory=lambda: {
        "CC0", "CC-BY", "CC-BY-SA", "MIT", "Apache-2.0", "proprietary-internal"})
    require_checksum: bool = True
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Reasoning", "Planning", "Knowledge"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Knowledge"})
    # Madde 24: bilgiyi çekirdeğe yalnız bunlar onaylayabilir
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors

    def evaluate(self, pack: "KnowledgePack") -> tuple[bool, list]:
        """DETERMİNİSTİK kalite & lisans & allowlist politikası. (compatible, reasons)."""
        reasons: list = []
        host = ""
        if pack.source_uri:
            try:
                host = (urlparse(pack.source_uri).hostname or "").lower()
            except Exception:  # noqa: BLE001 — bozuk uri güvenilmez sayılır
                host = ""
        publisher_ok = pack.publisher in self.trusted_publishers
        source_ok = host in self.trusted_sources if host else False
        if not (publisher_ok or source_ok):
            reasons.append("untrusted_source")
        if pack.license.strip() not in self.allowed_licenses:
            reasons.append("license_not_allowed")
        if self.require_checksum and not pack.checksum.strip():
            reasons.append("missing_checksum")
        if pack.kind not in PackKind.ALL:
            reasons.append("invalid_kind")
        return (len(reasons) == 0, reasons)


__all__ = [
    "PackKind", "PackStatus", "TRANSITIONS", "KnowledgePack", "KnowledgeMarketConfig",
    "KnowledgeMarketError", "ValidationError", "UnauthorizedError", "NotFoundError", "TransitionError",
]
