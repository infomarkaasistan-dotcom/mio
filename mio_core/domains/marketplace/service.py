"""MIO Core · Marketplace / Ecosystem Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

**Anayasa: denetlenmemiş üçüncü-taraf yetenek platforma SOKULAMAZ.** Listing registry + **deterministik uyumluluk
& allowlist politikası** + inceleme/kurulum durum makinesi. Onay yalnız approver (owner/Executive) — Madde 24;
uyumlu/güvenilir değilse otomatik reddedilir. Gerçek indirme/kurulum enjekte edilen kaynak adapter'a (DI) delege;
yoksa **no_connector** (uydurma sonuç YOK — Madde 8). Kurulum hatası **görünür** (install_failed — Madde 27).
Gerçek kurulum/çalıştırma çekirdekte YOK. authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, MarketplaceEvents, marketplace_contract
from .models import (
    Listing,
    ListingKind,
    ListingStatus,
    MarketplaceConfig,
    NotFoundError,
    TRANSITIONS,
    TransitionError,
    UnauthorizedError,
    ValidationError,
)
from .repository import MarketplaceRepository

logger = logging.getLogger("mio.domain.marketplace")

Installer = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MarketplaceDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: MarketplaceRepository, *, bus=None,
                 config: Optional[MarketplaceConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or MarketplaceConfig()
        self._installers: dict[str, tuple[Installer, str]] = {}   # kind -> (fn, adapter adı)
        self._metrics = {"submitted": 0, "approved": 0, "rejected": 0, "installed": 0,
                         "install_failed": 0, "no_connector": 0, "removed": 0}

    # ------------------------------------------------------------------ #
    def register_installer(self, kind: str, fn: Installer, *, name: str = "adapter") -> None:
        """Bir listing türü için GERÇEK indirme/kurulum connector'ı bağlar (kompozisyon-zamanı DI)."""
        if kind not in ListingKind.ALL:
            raise ValidationError(f"Geçersiz listing türü: {kind}")
        self._installers[kind] = (fn, name)

    def submit_listing(self, actor: str, name: str, *, kind: str = ListingKind.CAPABILITY,
                       publisher: str = "", version: str = "1.0.0", source_uri: str = "",
                       signature: str = "", description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "listing adı")
        if kind not in ListingKind.ALL:
            raise ValidationError(f"Geçersiz listing türü: {kind}")
        m = Listing(name=name, kind=kind, publisher=publisher, version=version, source_uri=source_uri,
                    signature=signature, description=description, status=ListingStatus.SUBMITTED)
        m.compatible, m.compat_reasons = self._cfg.evaluate(m)   # deterministik ön-değerlendirme
        self._repo.put(m)
        self._metrics["submitted"] += 1
        self._emit(MarketplaceEvents.LISTING_SUBMITTED, {"actor": actor, "id": m.id, "kind": kind,
                   "compatible": m.compatible})
        return m.to_dict()

    def check_compatibility(self, actor: str, listing_id: str) -> dict[str, Any]:
        """DETERMİNİSTİK uyumluluk raporu (salt-okunur)."""
        self._authorize(actor)
        m = self._require_listing(listing_id)
        compatible, reasons = self._cfg.evaluate(m)
        return {"id": m.id, "compatible": compatible, "reasons": reasons}

    def approve(self, actor: str, listing_id: str) -> dict[str, Any]:
        """Üçüncü-taraf yeteneği onaylar (Madde 24; yalnız approver). Uyumsuz/güvenilmezse OTOMATİK reddeder."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' listing onaylayamaz (Madde 24)")
        m = self._require_listing(listing_id)
        compatible, reasons = self._cfg.evaluate(m)
        m.compatible, m.compat_reasons = compatible, reasons
        if not compatible:                       # denetlenmemiş/güvenilmez → platforma sokulamaz
            self._set_status(m, ListingStatus.REJECTED)
            m.rejected_reason = ",".join(reasons)
            self._repo.put(m)
            self._metrics["rejected"] += 1
            self._emit(MarketplaceEvents.LISTING_REJECTED, {"id": m.id, "reasons": reasons})
            return {"approved": False, "status": m.status, "reasons": reasons, "listing": m.to_dict()}
        self._set_status(m, ListingStatus.APPROVED)
        m.approved_by = actor
        self._repo.put(m)
        self._metrics["approved"] += 1
        self._emit(MarketplaceEvents.LISTING_APPROVED, {"id": m.id, "by": actor})
        return {"approved": True, "status": m.status, "listing": m.to_dict()}

    def reject(self, actor: str, listing_id: str, *, reason: str = "") -> dict[str, Any]:
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' listing reddedemez (Madde 24)")
        m = self._require_listing(listing_id)
        self._set_status(m, ListingStatus.REJECTED)
        m.rejected_reason = (reason or "manual_reject").strip()
        self._repo.put(m)
        self._metrics["rejected"] += 1
        self._emit(MarketplaceEvents.LISTING_REJECTED, {"id": m.id, "reasons": [m.rejected_reason]})
        return m.to_dict()

    def install(self, actor: str, listing_id: str) -> dict[str, Any]:
        """Yalnız APPROVED listing kurulur — kaynak adapter'a delege. Yoksa no_connector (APPROVED kalır)."""
        self._authorize_writer(actor)
        m = self._require_listing(listing_id)
        if m.status != ListingStatus.APPROVED:
            raise TransitionError(f"Yalnız 'approved' kurulabilir (durum: {m.status})")
        entry = self._installers.get(m.kind)
        if entry is None:                       # DÜRÜST: gerçek kaynak adapter'ı bağlı değil
            self._metrics["no_connector"] += 1
            self._emit(MarketplaceEvents.NO_CONNECTOR, {"id": m.id, "kind": m.kind})
            return {"installed": False, "reason": "no_connector", "status": m.status, "listing": m.to_dict()}
        fn, cname = entry
        try:
            result = fn({"listing": m.to_dict()}) or {}
        except Exception as exc:  # noqa: BLE001 — kurulum hatası GÖRÜNÜR olur (Madde 27), sistemi bozmaz
            self._metrics["install_failed"] += 1
            err = str(exc)[:300]
            self._emit(MarketplaceEvents.INSTALL_FAILED, {"id": m.id, "error": err})
            return {"installed": False, "reason": "failed", "error": err, "status": m.status,
                    "listing": m.to_dict()}
        self._set_status(m, ListingStatus.INSTALLED)
        m.install_ref = str(result.get("install_ref", ""))
        m.connector = cname
        self._repo.put(m)
        self._metrics["installed"] += 1
        self._emit(MarketplaceEvents.INSTALLED, {"id": m.id, "connector": cname})
        return {"installed": True, "reason": "ok", "status": m.status, "listing": m.to_dict()}

    def remove(self, actor: str, listing_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        m = self._require_listing(listing_id)
        self._set_status(m, ListingStatus.REMOVED)
        self._repo.put(m)
        self._metrics["removed"] += 1
        self._emit(MarketplaceEvents.REMOVED, {"id": m.id})
        return m.to_dict()

    # -- sorgular -------------------------------------------------------- #
    def get_listing(self, actor: str, listing_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_listing(listing_id).to_dict()

    def list_listings(self, actor: str, *, kind: Optional[str] = None,
                      status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in ListingKind.ALL:
            raise ValidationError(f"Geçersiz listing türü: {kind}")
        if status is not None and status not in ListingStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [m.to_dict() for m in self._repo.all(kind=kind, status=status)]

    def installers(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"available": sorted(self._installers), "all_kinds": sorted(ListingKind.ALL),
                "missing": sorted(ListingKind.ALL - set(self._installers))}

    def stats(self) -> dict[str, Any]:
        return {"listings": self._repo.count(), "approved": self._repo.count(status=ListingStatus.APPROVED),
                "installed": self._repo.count(status=ListingStatus.INSTALLED),
                "rejected": self._repo.count(status=ListingStatus.REJECTED),
                "installers": len(self._installers), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return marketplace_contract()

    # ------------------------------------------------------------------ #
    def _set_status(self, m: Listing, target: str) -> None:
        if target != m.status and target not in TRANSITIONS.get(m.status, set()):
            raise TransitionError(f"Geçersiz yaşam-döngüsü geçişi: {m.status} → {target}")
        m.status = target
        m.updated_at = _now()

    def _require_listing(self, listing_id: str) -> Listing:
        m = self._repo.get(listing_id)
        if m is None:
            raise NotFoundError(f"Listing bulunamadı: {listing_id}")
        return m

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' marketplace erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' marketplace yönetimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
