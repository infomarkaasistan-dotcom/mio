"""MIO Core · Extension SDK Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

**Anayasa: denetlenmemiş/aşırı-izinli üçüncü-taraf uzantı platforma SOKULAMAZ; etkinleştirme ONAY ister (Madde 24).**
Uzantı manifest registry + **deterministik manifest & izin-kapsamı doğrulama** + uzantı yaşam-döngüsü. Etkinleştirme
yalnız approver (owner/Executive); uyumsuz/aşırı-izinli otomatik reddedilir. En-az-yetki: yalnız istenen+izinli
izinler verilir. Uzantı çalıştırma enjekte edilen host sandbox adapter'a (DI) delege; yoksa **no_connector**
(uydurma sonuç YOK — Madde 8). Gerçek yürütme çekirdekte YOK. authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, ExtensionEvents, extension_contract
from .models import (
    ExtKind,
    ExtStatus,
    Extension,
    ExtensionConfig,
    NotFoundError,
    TRANSITIONS,
    TransitionError,
    UnauthorizedError,
    ValidationError,
)
from .repository import ExtensionRepository

logger = logging.getLogger("mio.domain.extension_sdk")

Host = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExtensionSDKDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: ExtensionRepository, *, bus=None,
                 config: Optional[ExtensionConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or ExtensionConfig()
        self._hosts: dict[str, tuple[Host, str]] = {}   # ext kind -> (fn, sandbox adapter adı)
        self._metrics = {"registered": 0, "validated": 0, "rejected": 0, "enabled": 0, "disabled": 0,
                         "invoked": 0, "invoke_failed": 0, "no_connector": 0}

    # ------------------------------------------------------------------ #
    def register_host(self, kind: str, fn: Host, *, name: str = "sandbox") -> None:
        """Bir uzantı türü için GERÇEK host sandbox çalıştırma connector'ı bağlar (kompozisyon-zamanı DI)."""
        if kind not in ExtKind.ALL:
            raise ValidationError(f"Geçersiz uzantı türü: {kind}")
        self._hosts[kind] = (fn, name)

    def register_extension(self, actor: str, name: str, *, kind: str = ExtKind.TOOL, version: str = "1.0.0",
                           entry: str = "", publisher: str = "", signature: str = "",
                           requested_permissions: Optional[list] = None,
                           description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "uzantı adı")
        if kind not in ExtKind.ALL:
            raise ValidationError(f"Geçersiz uzantı türü: {kind}")
        ext = Extension(name=name, kind=kind, version=version, entry=entry, publisher=publisher,
                        signature=signature, requested_permissions=list(requested_permissions or []),
                        description=description, status=ExtStatus.REGISTERED)
        ext.valid, ext.validation_reasons = self._cfg.evaluate(ext)   # deterministik ön-değerlendirme
        self._repo.put(ext)
        self._metrics["registered"] += 1
        self._emit(ExtensionEvents.REGISTERED, {"actor": actor, "id": ext.id, "kind": kind,
                   "valid": ext.valid})
        return ext.to_dict()

    def validate(self, actor: str, ext_id: str) -> dict[str, Any]:
        """DETERMİNİSTİK manifest+izin doğrulama. Uyumsuz/aşırı-izinli → OTOMATİK reddeder."""
        self._authorize_writer(actor)
        ext = self._require_ext(ext_id)
        valid, reasons = self._cfg.evaluate(ext)
        ext.valid, ext.validation_reasons = valid, reasons
        if not valid:
            self._set_status(ext, ExtStatus.REJECTED)
            ext.rejected_reason = ",".join(reasons)
            self._repo.put(ext)
            self._metrics["rejected"] += 1
            self._emit(ExtensionEvents.REJECTED, {"id": ext.id, "reasons": reasons})
            return {"validated": False, "status": ext.status, "reasons": reasons, "extension": ext.to_dict()}
        self._set_status(ext, ExtStatus.VALIDATED)
        self._repo.put(ext)
        self._metrics["validated"] += 1
        self._emit(ExtensionEvents.VALIDATED, {"id": ext.id})
        return {"validated": True, "status": ext.status, "extension": ext.to_dict()}

    def enable(self, actor: str, ext_id: str) -> dict[str, Any]:
        """Uzantıyı etkinleştirir (Madde 24; yalnız approver). Uyumsuzsa OTOMATİK reddeder; en-az-yetki verir."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' uzantı etkinleştiremez (Madde 24)")
        ext = self._require_ext(ext_id)
        if ext.status not in (ExtStatus.VALIDATED, ExtStatus.DISABLED):
            raise TransitionError(f"Yalnız 'validated'/'disabled' etkinleştirilir (durum: {ext.status})")
        valid, reasons = self._cfg.evaluate(ext)     # onay anında yeniden doğrula (defense-in-depth)
        ext.valid, ext.validation_reasons = valid, reasons
        if not valid:
            self._set_status(ext, ExtStatus.REJECTED)
            ext.rejected_reason = ",".join(reasons)
            self._repo.put(ext)
            self._metrics["rejected"] += 1
            self._emit(ExtensionEvents.REJECTED, {"id": ext.id, "reasons": reasons})
            return {"enabled": False, "status": ext.status, "reasons": reasons, "extension": ext.to_dict()}
        self._set_status(ext, ExtStatus.ENABLED)
        ext.approved_by = actor
        # en-az-yetki: yalnız istenen + izinli izinler verilir
        ext.granted_permissions = [p for p in ext.requested_permissions
                                   if p in self._cfg.allowed_permissions]
        self._repo.put(ext)
        self._metrics["enabled"] += 1
        self._emit(ExtensionEvents.ENABLED, {"id": ext.id, "by": actor,
                   "granted": list(ext.granted_permissions)})
        return {"enabled": True, "status": ext.status, "extension": ext.to_dict()}

    def disable(self, actor: str, ext_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        ext = self._require_ext(ext_id)
        self._set_status(ext, ExtStatus.DISABLED)
        ext.granted_permissions = []                 # izinler geri alınır
        self._repo.put(ext)
        self._metrics["disabled"] += 1
        self._emit(ExtensionEvents.DISABLED, {"id": ext.id})
        return ext.to_dict()

    def invoke(self, actor: str, ext_id: str, payload: Optional[dict] = None) -> dict[str, Any]:
        """Yalnız ENABLED uzantıyı host sandbox'a delege ederek çağırır. Host yoksa DÜRÜST no_connector."""
        self._authorize_writer(actor)
        ext = self._require_ext(ext_id)
        if ext.status != ExtStatus.ENABLED:
            raise TransitionError(f"Yalnız 'enabled' uzantı çağrılır (durum: {ext.status})")
        entry = self._hosts.get(ext.kind)
        if entry is None:                       # DÜRÜST: gerçek host sandbox bağlı değil
            self._metrics["no_connector"] += 1
            self._emit(ExtensionEvents.NO_CONNECTOR, {"id": ext.id, "kind": ext.kind})
            return {"invoked": False, "reason": "no_connector", "result": {}, "extension_id": ext.id}
        fn, cname = entry
        try:
            result = fn({"extension": ext.to_dict(), "granted_permissions": list(ext.granted_permissions),
                         "payload": dict(payload or {})}) or {}
            self._metrics["invoked"] += 1
            self._emit(ExtensionEvents.INVOKED, {"id": ext.id, "connector": cname})
            return {"invoked": True, "reason": "ok", "result": dict(result), "connector": cname,
                    "extension_id": ext.id}
        except Exception as exc:  # noqa: BLE001 — uzantı hatası çağrıya dönüşür (görünür), sistemi bozmaz
            self._metrics["invoke_failed"] += 1
            err = str(exc)[:300]
            self._emit(ExtensionEvents.INVOKE_FAILED, {"id": ext.id, "error": err})
            return {"invoked": False, "reason": "failed", "error": err, "extension_id": ext.id}

    # -- sorgular -------------------------------------------------------- #
    def get_extension(self, actor: str, ext_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_ext(ext_id).to_dict()

    def list_extensions(self, actor: str, *, kind: Optional[str] = None,
                        status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in ExtKind.ALL:
            raise ValidationError(f"Geçersiz uzantı türü: {kind}")
        if status is not None and status not in ExtStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [e.to_dict() for e in self._repo.all(kind=kind, status=status)]

    def hosts(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"available": sorted(self._hosts), "all_kinds": sorted(ExtKind.ALL),
                "missing": sorted(ExtKind.ALL - set(self._hosts))}

    def permissions_catalog(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"grantable": sorted(self._cfg.allowed_permissions)}

    def stats(self) -> dict[str, Any]:
        return {"extensions": self._repo.count(), "enabled": self._repo.count(status=ExtStatus.ENABLED),
                "rejected": self._repo.count(status=ExtStatus.REJECTED), "hosts": len(self._hosts),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return extension_contract()

    # ------------------------------------------------------------------ #
    def _set_status(self, ext: Extension, target: str) -> None:
        if target != ext.status and target not in TRANSITIONS.get(ext.status, set()):
            raise TransitionError(f"Geçersiz yaşam-döngüsü geçişi: {ext.status} → {target}")
        ext.status = target
        ext.updated_at = _now()

    def _require_ext(self, ext_id: str) -> Extension:
        e = self._repo.get(ext_id)
        if e is None:
            raise NotFoundError(f"Uzantı bulunamadı: {ext_id}")
        return e

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' uzantı erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' uzantı yönetimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
