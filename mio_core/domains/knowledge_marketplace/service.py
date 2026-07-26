"""MIO Core · Knowledge Marketplace Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

**Anayasa: denetlenmemiş bilgi Knowledge Domain'e/çekirdeğe SOKULAMAZ.** Bilgi paketi registry + **deterministik
kalite & lisans & allowlist politikası** + import durum makinesi + **provenance etiketi**. Onay yalnız approver
(owner/Executive) — Madde 24; uyumsuz/lisanssız otomatik reddedilir. Gerçek indirme/import enjekte edilen kaynak
adapter'a (DI) delege; yoksa **no_connector** (uydurma sonuç YOK — Madde 8). Import hatası **görünür**
(import_failed — Madde 27). Gerçek indirme/çalıştırma çekirdekte YOK. authz · validation · events · observability ·
errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, KnowledgeMarketEvents, knowledge_market_contract
from .models import (
    KnowledgeMarketConfig,
    KnowledgePack,
    NotFoundError,
    PackKind,
    PackStatus,
    TRANSITIONS,
    TransitionError,
    UnauthorizedError,
    ValidationError,
)
from .repository import KnowledgeMarketRepository

logger = logging.getLogger("mio.domain.knowledge_marketplace")

Source = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class KnowledgeMarketplaceDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: KnowledgeMarketRepository, *, bus=None,
                 config: Optional[KnowledgeMarketConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or KnowledgeMarketConfig()
        self._sources: dict[str, tuple[Source, str]] = {}   # kind -> (fn, adapter adı)
        self._metrics = {"submitted": 0, "approved": 0, "rejected": 0, "imported": 0,
                         "import_failed": 0, "no_connector": 0, "removed": 0}

    # ------------------------------------------------------------------ #
    def register_source(self, kind: str, fn: Source, *, name: str = "adapter") -> None:
        """Bir pack türü için GERÇEK indirme/import connector'ı bağlar (kompozisyon-zamanı DI)."""
        if kind not in PackKind.ALL:
            raise ValidationError(f"Geçersiz pack türü: {kind}")
        self._sources[kind] = (fn, name)

    def submit_pack(self, actor: str, name: str, *, kind: str = PackKind.FACT_SET, publisher: str = "",
                    version: str = "1.0.0", license: str = "", source_uri: str = "", checksum: str = "",
                    item_count: int = 0, description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "pack adı")
        if kind not in PackKind.ALL:
            raise ValidationError(f"Geçersiz pack türü: {kind}")
        p = KnowledgePack(name=name, kind=kind, publisher=publisher, version=version, license=license,
                          source_uri=source_uri, checksum=checksum, item_count=int(item_count),
                          description=description, status=PackStatus.SUBMITTED)
        p.compatible, p.compat_reasons = self._cfg.evaluate(p)   # deterministik ön-değerlendirme
        self._repo.put(p)
        self._metrics["submitted"] += 1
        self._emit(KnowledgeMarketEvents.PACK_SUBMITTED, {"actor": actor, "id": p.id, "kind": kind,
                   "compatible": p.compatible})
        return p.to_dict()

    def check_compatibility(self, actor: str, pack_id: str) -> dict[str, Any]:
        """DETERMİNİSTİK uyumluluk raporu (salt-okunur)."""
        self._authorize(actor)
        p = self._require_pack(pack_id)
        compatible, reasons = self._cfg.evaluate(p)
        return {"id": p.id, "compatible": compatible, "reasons": reasons}

    def approve(self, actor: str, pack_id: str) -> dict[str, Any]:
        """Bilgiyi çekirdeğe kabul için onaylar (Madde 24; approver). Uyumsuz/lisanssız → OTOMATİK reddeder."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' bilgi paketi onaylayamaz (Madde 24)")
        p = self._require_pack(pack_id)
        compatible, reasons = self._cfg.evaluate(p)
        p.compatible, p.compat_reasons = compatible, reasons
        if not compatible:                       # denetlenmemiş/lisanssız → Knowledge'a sokulamaz
            self._set_status(p, PackStatus.REJECTED)
            p.rejected_reason = ",".join(reasons)
            self._repo.put(p)
            self._metrics["rejected"] += 1
            self._emit(KnowledgeMarketEvents.PACK_REJECTED, {"id": p.id, "reasons": reasons})
            return {"approved": False, "status": p.status, "reasons": reasons, "pack": p.to_dict()}
        self._set_status(p, PackStatus.APPROVED)
        p.approved_by = actor
        self._repo.put(p)
        self._metrics["approved"] += 1
        self._emit(KnowledgeMarketEvents.PACK_APPROVED, {"id": p.id, "by": actor})
        return {"approved": True, "status": p.status, "pack": p.to_dict()}

    def reject(self, actor: str, pack_id: str, *, reason: str = "") -> dict[str, Any]:
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' bilgi paketi reddedemez (Madde 24)")
        p = self._require_pack(pack_id)
        self._set_status(p, PackStatus.REJECTED)
        p.rejected_reason = (reason or "manual_reject").strip()
        self._repo.put(p)
        self._metrics["rejected"] += 1
        self._emit(KnowledgeMarketEvents.PACK_REJECTED, {"id": p.id, "reasons": [p.rejected_reason]})
        return p.to_dict()

    def import_pack(self, actor: str, pack_id: str) -> dict[str, Any]:
        """Yalnız APPROVED pack import edilir — kaynak adapter'a delege + provenance etiketi. Yoksa no_connector."""
        self._authorize_writer(actor)
        p = self._require_pack(pack_id)
        if p.status != PackStatus.APPROVED:
            raise TransitionError(f"Yalnız 'approved' import edilebilir (durum: {p.status})")
        entry = self._sources.get(p.kind)
        if entry is None:                       # DÜRÜST: gerçek kaynak adapter'ı bağlı değil
            self._metrics["no_connector"] += 1
            self._emit(KnowledgeMarketEvents.NO_CONNECTOR, {"id": p.id, "kind": p.kind})
            return {"imported": False, "reason": "no_connector", "status": p.status, "pack": p.to_dict()}
        fn, cname = entry
        try:
            result = fn({"pack": p.to_dict()}) or {}
        except Exception as exc:  # noqa: BLE001 — import hatası GÖRÜNÜR olur (Madde 27), sistemi bozmaz
            self._metrics["import_failed"] += 1
            err = str(exc)[:300]
            self._emit(KnowledgeMarketEvents.IMPORT_FAILED, {"id": p.id, "error": err})
            return {"imported": False, "reason": "failed", "error": err, "status": p.status,
                    "pack": p.to_dict()}
        self._set_status(p, PackStatus.IMPORTED)
        p.imported_ref = str(result.get("imported_ref", ""))
        p.imported_items = int(result.get("imported_items", 0))
        p.connector = cname
        p.provenance = {"publisher": p.publisher, "source_uri": p.source_uri, "license": p.license,
                        "version": p.version, "checksum": p.checksum, "imported_at": _now(),
                        "approved_by": p.approved_by}   # izlenebilirlik
        self._repo.put(p)
        self._metrics["imported"] += 1
        self._emit(KnowledgeMarketEvents.IMPORTED, {"id": p.id, "connector": cname,
                   "items": p.imported_items})
        return {"imported": True, "reason": "ok", "status": p.status, "pack": p.to_dict()}

    def remove(self, actor: str, pack_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        p = self._require_pack(pack_id)
        self._set_status(p, PackStatus.REMOVED)
        self._repo.put(p)
        self._metrics["removed"] += 1
        self._emit(KnowledgeMarketEvents.REMOVED, {"id": p.id})
        return p.to_dict()

    # -- sorgular -------------------------------------------------------- #
    def get_pack(self, actor: str, pack_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_pack(pack_id).to_dict()

    def list_packs(self, actor: str, *, kind: Optional[str] = None,
                   status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in PackKind.ALL:
            raise ValidationError(f"Geçersiz pack türü: {kind}")
        if status is not None and status not in PackStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [p.to_dict() for p in self._repo.all(kind=kind, status=status)]

    def sources(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"available": sorted(self._sources), "all_kinds": sorted(PackKind.ALL),
                "missing": sorted(PackKind.ALL - set(self._sources))}

    def stats(self) -> dict[str, Any]:
        return {"packs": self._repo.count(), "approved": self._repo.count(status=PackStatus.APPROVED),
                "imported": self._repo.count(status=PackStatus.IMPORTED),
                "rejected": self._repo.count(status=PackStatus.REJECTED),
                "sources": len(self._sources), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return knowledge_market_contract()

    # ------------------------------------------------------------------ #
    def _set_status(self, p: KnowledgePack, target: str) -> None:
        if target != p.status and target not in TRANSITIONS.get(p.status, set()):
            raise TransitionError(f"Geçersiz yaşam-döngüsü geçişi: {p.status} → {target}")
        p.status = target
        p.updated_at = _now()

    def _require_pack(self, pack_id: str) -> KnowledgePack:
        p = self._repo.get(pack_id)
        if p is None:
            raise NotFoundError(f"Bilgi paketi bulunamadı: {pack_id}")
        return p

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' knowledge marketplace erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' bilgi paketi yönetimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
