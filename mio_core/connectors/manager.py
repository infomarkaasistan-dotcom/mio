"""MIO Core · Connector Manager — capability → connector DISPATCH, DETERMİNİSTİK, LLM-BAĞIMSIZ.

**Executive yalnız `execute(capability, request)` çağırır**; Manager hangi connector'ın çalışacağına karar verir
(registry'den öncelik sırası + health). İlk uygun sağlayıcı çalışır; başarısız olursa bir sonrakine **failover**
(Madde 28 capability failover). **Connector yoksa ÇÖKMEZ** → `connector_unavailable` (Madde 8; Executive çalışmaya
devam eder). Yüksek-risk/geri-alınamaz capability onaysız çalışmaz (Madde 24). İş mantığı connector adapter'da;
burada yalnız güvenli orkestrasyon."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, ConnectorEvents, connector_contract
from .models import (
    CallableConnector,
    ConnectorConfig,
    Outcome,
    executed_result,
    failed_result,
    requires_approval_result,
    unavailable_result,
)
from .registry import ConnectorRegistry

logger = logging.getLogger("mio.connectors")


class ConnectorManager:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, registry: ConnectorRegistry, *, bus=None,
                 config: Optional[ConnectorConfig] = None) -> None:
        self._registry = registry
        self._bus = bus
        self._cfg = config or ConnectorConfig()
        self._metrics = {"executed": 0, "unavailable": 0, "requires_approval": 0, "failed": 0,
                         "failover": 0}

    @property
    def registry(self) -> ConnectorRegistry:
        return self._registry

    def register(self, connector: CallableConnector) -> None:
        """Kolaylık: connector'ı registry'ye kaydeder (manager üzerinden)."""
        self._registry.register(connector)

    def execute(self, capability: str, request: Optional[dict] = None, *, actor: str = "owner",
                user_approved: bool = False) -> dict[str, Any]:
        """capability'yi çalıştırır. ASLA raise ETMEZ — her durumda yapılandırılmış sonuç döner (çökmez)."""
        capability = (capability or "").strip()
        if not capability:
            return {"ok": False, "status": Outcome.FAILED, "capability": capability,
                    "errors": [{"error": "capability boş"}]}

        providers = self._registry.providers_for(capability)
        if not providers:                          # DÜRÜST: capability'yi sağlayan connector yok
            self._metrics["unavailable"] += 1
            self._emit(ConnectorEvents.UNAVAILABLE, {"capability": capability, "actor": actor})
            return unavailable_result(capability)

        if self._cfg.is_high_risk(capability) and not user_approved:   # Madde 24
            self._metrics["requires_approval"] += 1
            self._emit(ConnectorEvents.REQUIRES_APPROVAL, {"capability": capability, "actor": actor})
            return requires_approval_result(capability)

        # sağlıklı olanları öne al; hiçbiri sağlıklı değilse yine de dene (dürüst deneme)
        healthy = [c for c in providers if c.health().ok]
        ordered = healthy or providers
        errors: list = []
        for connector in ordered:
            try:
                result = connector.execute(capability, dict(request or {}))
                self._metrics["executed"] += 1
                self._emit(ConnectorEvents.EXECUTED, {"capability": capability, "connector": connector.name})
                return executed_result(capability, connector.name, result)
            except Exception as exc:  # noqa: BLE001 — sağlayıcı hatası → failover, sistemi bozmaz
                errors.append({"connector": connector.name, "error": str(exc)[:200]})
                self._metrics["failover"] += 1
                self._emit(ConnectorEvents.FAILOVER, {"capability": capability, "connector": connector.name,
                           "error": str(exc)[:120]})
                continue
        self._metrics["failed"] += 1               # tüm sağlayıcılar başarısız
        self._emit(ConnectorEvents.FAILED, {"capability": capability, "attempts": len(ordered)})
        return failed_result(capability, errors)

    def available(self, capability: str) -> bool:
        return self._registry.has_capability(capability)

    def stats(self) -> dict[str, Any]:
        return {**self._registry.stats(), **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return connector_contract()

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)


__all__ = ["ConnectorManager"]
