"""MIO Core · Model Management Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

**Anayasa: model seçimi DETERMİNİSTİK politikadır; LLM danışman, karar verici DEĞİL.** Model registry + sürüm +
yaşam-döngüsü durum makinesi (registered→available→deprecated→retired) + deterministik seçim (priority/context/
cost) + sağlayıcı connector routing. Gerçek indirme/serve enjekte edilen provider adapter'a (DI) delege; provider
yoksa **no_connector** → model `available` OLMAZ (uydurma sonuç YOK — Madde 8). Provider hatası **görünür**
(provision_failed — Madde 27). Model **çalıştırma** çekirdekte YOK. Retire (yetenek kaybı) ONAY ister (Madde 24).
authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, ModelEvents, model_contract
from .models import (
    Lifecycle,
    Location,
    Model,
    ModelKind,
    ModelMgmtConfig,
    NotFoundError,
    TRANSITIONS,
    TransitionError,
    UnauthorizedError,
    ValidationError,
    selection_score,
)
from .repository import ModelRepository

logger = logging.getLogger("mio.domain.model_management")

Provider = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModelManagementDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: ModelRepository, *, bus=None,
                 config: Optional[ModelMgmtConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or ModelMgmtConfig()
        self._providers: dict[str, tuple[Provider, str]] = {}   # provider adı -> (fn, adapter adı)
        self._metrics = {"registered": 0, "provisioned": 0, "no_connector": 0, "provision_failed": 0,
                         "selected": 0, "deprecated": 0, "reactivated": 0, "retired": 0}

    # ------------------------------------------------------------------ #
    def register_provider(self, provider: str, fn: Provider, *, name: str = "adapter") -> None:
        """Bir sağlayıcı için GERÇEK indirme/serve connector'ı bağlar (kompozisyon-zamanı DI)."""
        provider = self._require(provider, "sağlayıcı")
        self._providers[provider] = (fn, name)

    def register_model(self, actor: str, name: str, *, kind: str = ModelKind.LLM, provider: str = "",
                       location: str = Location.REMOTE, version: str = "1.0.0", context_window: int = 0,
                       cost_per_1k: float = 0.0, priority: int = 100,
                       description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "model adı")
        if kind not in ModelKind.ALL:
            raise ValidationError(f"Geçersiz model türü: {kind}")
        if location not in Location.ALL:
            raise ValidationError(f"Geçersiz konum: {location}")
        m = Model(name=name, kind=kind, provider=provider, location=location, version=version,
                  context_window=int(context_window), cost_per_1k=float(cost_per_1k),
                  priority=int(priority), description=description, status=Lifecycle.REGISTERED)
        self._repo.put(m)
        self._metrics["registered"] += 1
        self._emit(ModelEvents.MODEL_REGISTERED, {"actor": actor, "id": m.id, "kind": kind})
        return m.to_dict()

    def provision(self, actor: str, model_id: str) -> dict[str, Any]:
        """Modeli sağlar (indir/serve) — provider adapter'a delege. Yoksa no_connector; model available OLMAZ."""
        self._authorize_writer(actor)
        m = self._require_model(model_id)
        if m.status == Lifecycle.RETIRED:
            raise TransitionError("Emekli model provision edilemez")
        entry = self._providers.get(m.provider)
        if entry is None:                       # DÜRÜST: gerçek provider adapter'ı bağlı değil
            self._metrics["no_connector"] += 1
            self._emit(ModelEvents.NO_CONNECTOR, {"id": m.id, "provider": m.provider})
            return {"provisioned": False, "reason": "no_connector", "status": m.status, "model": m.to_dict()}
        fn, name = entry
        try:
            result = fn({"model": m.to_dict()}) or {}
        except Exception as exc:  # noqa: BLE001 — provider hatası GÖRÜNÜR olur (Madde 27), sistemi bozmaz
            self._metrics["provision_failed"] += 1
            err = str(exc)[:300]
            self._emit(ModelEvents.PROVISION_FAILED, {"id": m.id, "error": err})
            return {"provisioned": False, "reason": "failed", "error": err, "status": m.status,
                    "model": m.to_dict()}
        self._set_status(m, Lifecycle.AVAILABLE)
        m.endpoint = str(result.get("endpoint", ""))
        m.connector = name
        self._repo.put(m)
        self._metrics["provisioned"] += 1
        self._emit(ModelEvents.MODEL_PROVISIONED, {"id": m.id, "connector": name})
        return {"provisioned": True, "reason": "ok", "status": m.status, "model": m.to_dict()}

    def select(self, actor: str, kind: str, *, min_context: int = 0, location: Optional[str] = None,
               provider: Optional[str] = None) -> Optional[dict[str, Any]]:
        """DETERMİNİSTİK model seçimi (LLM'siz): yalnız 'available' + kısıtları sağlayan en iyi skor."""
        self._authorize(actor)
        if kind not in ModelKind.ALL:
            raise ValidationError(f"Geçersiz model türü: {kind}")
        candidates = [m for m in self._repo.all(kind=kind, status=Lifecycle.AVAILABLE)
                      if m.context_window >= int(min_context)
                      and (location is None or m.location == location)
                      and (provider is None or m.provider == provider)]
        if not candidates:
            return None
        chosen = max(candidates, key=selection_score)
        self._metrics["selected"] += 1
        self._emit(ModelEvents.MODEL_SELECTED, {"id": chosen.id, "kind": kind, "name": chosen.name})
        return chosen.to_dict()

    # -- yaşam-döngüsü geçişleri ---------------------------------------- #
    def deprecate(self, actor: str, model_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        m = self._require_model(model_id)
        self._set_status(m, Lifecycle.DEPRECATED)
        self._repo.put(m)
        self._metrics["deprecated"] += 1
        self._emit(ModelEvents.MODEL_DEPRECATED, {"id": m.id})
        return m.to_dict()

    def reactivate(self, actor: str, model_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        m = self._require_model(model_id)
        self._set_status(m, Lifecycle.AVAILABLE)
        self._repo.put(m)
        self._metrics["reactivated"] += 1
        self._emit(ModelEvents.MODEL_REACTIVATED, {"id": m.id})
        return m.to_dict()

    def retire(self, actor: str, model_id: str) -> dict[str, Any]:
        """Emekliye ayırma = yetenek kaybı → ONAY ister (Madde 24). Yalnız approver (owner/Executive) yürütür."""
        self._authorize_writer(actor)
        m = self._require_model(model_id)
        if m.status == Lifecycle.RETIRED:
            raise TransitionError("Model zaten emekli")
        if not self._cfg.is_approver(actor):     # Madde 24: onaysız kalıcı devre dışı bırakılamaz
            self._metrics_bump("approval_required")
            self._emit(ModelEvents.RETIRE_APPROVAL_REQUIRED, {"id": m.id, "actor": actor})
            return {"retired": False, "requires_approval": True, "status": m.status, "model": m.to_dict()}
        self._set_status(m, Lifecycle.RETIRED)
        self._repo.put(m)
        self._metrics["retired"] += 1
        self._emit(ModelEvents.MODEL_RETIRED, {"id": m.id, "by": actor})
        return {"retired": True, "requires_approval": False, "status": m.status, "model": m.to_dict()}

    # -- sorgular -------------------------------------------------------- #
    def get_model(self, actor: str, model_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_model(model_id).to_dict()

    def list_models(self, actor: str, *, kind: Optional[str] = None,
                    status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in ModelKind.ALL:
            raise ValidationError(f"Geçersiz model türü: {kind}")
        if status is not None and status not in Lifecycle.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [m.to_dict() for m in self._repo.all(kind=kind, status=status)]

    def providers(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"available": sorted(self._providers)}

    def stats(self) -> dict[str, Any]:
        return {"models": self._repo.count(), "available": self._repo.count(status=Lifecycle.AVAILABLE),
                "retired": self._repo.count(status=Lifecycle.RETIRED), "providers": len(self._providers),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return model_contract()

    # ------------------------------------------------------------------ #
    def _set_status(self, m: Model, target: str) -> None:
        if target != m.status and target not in TRANSITIONS.get(m.status, set()):
            raise TransitionError(f"Geçersiz yaşam-döngüsü geçişi: {m.status} → {target}")
        m.status = target
        m.updated_at = _now()

    def _require_model(self, model_id: str) -> Model:
        m = self._repo.get(model_id)
        if m is None:
            raise NotFoundError(f"Model bulunamadı: {model_id}")
        return m

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' model erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' model yönetimi için yetkili değil")

    def _metrics_bump(self, key: str) -> None:
        self._metrics[key] = self._metrics.get(key, 0) + 1

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
