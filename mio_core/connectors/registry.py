"""MIO Core · Capability Registry — hangi connector yüklü, hangi capability'yi sağlıyor, öncelik, health.

Connector'lar buraya KAYIT olur. Capability ile sorgulanır (isimle değil): `providers_for(capability)` öncelik
sırasıyla döner. Böylece ileride connector değiştirmek gerekmez — capability sabit kalır, sağlayıcı değişir.
DETERMİNİSTİK sıralama (priority↓, name↑); LLM yok."""

from __future__ import annotations

import threading
from typing import Any, Optional

from .models import CallableConnector, ConnectorCategory, ValidationError


class ConnectorRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connectors: dict[str, CallableConnector] = {}

    def register(self, connector: CallableConnector) -> None:
        """Bir connector'ı kaydeder (kompozisyon-zamanı ya da çalışma-zamanı DI)."""
        if not hasattr(connector, "capabilities") or not connector.capabilities:
            raise ValidationError("connector en az bir capability sağlamalı")
        with self._lock:
            self._connectors[connector.name] = connector

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._connectors.pop(name, None) is not None

    def get(self, name: str) -> Optional[CallableConnector]:
        return self._connectors.get(name)

    def all(self) -> list[CallableConnector]:
        return list(self._connectors.values())

    def providers_for(self, capability: str) -> list[CallableConnector]:
        """capability'yi sağlayan connector'lar — DETERMİNİSTİK sıra (priority↓, name↑). İlk uygun çalışır."""
        matches = [c for c in self._connectors.values() if c.provides(capability)]
        return sorted(matches, key=lambda c: (-c.priority, c.name))

    def capabilities(self) -> dict[str, list[str]]:
        """capability → onu sağlayan connector adları (öncelik sırasıyla)."""
        out: dict[str, list[str]] = {}
        for c in self._connectors.values():
            for cap in c.capabilities:
                out.setdefault(cap, [])
        for cap in out:
            out[cap] = [c.name for c in self.providers_for(cap)]
        return out

    def has_capability(self, capability: str) -> bool:
        return any(c.provides(capability) for c in self._connectors.values())

    def overview(self) -> list[dict[str, Any]]:
        """Kayıtlı connector'ların özeti (ad/kategori/capability/öncelik/health)."""
        return [c.to_dict() for c in sorted(self._connectors.values(),
                                            key=lambda c: (c.category, -c.priority, c.name))]

    def health(self) -> dict[str, Any]:
        per = {c.name: c.health().to_dict() for c in self._connectors.values()}
        unhealthy = [n for n, h in per.items() if not h["ok"]]
        return {"connectors": len(per), "unhealthy": unhealthy, "detail": per}

    def stats(self) -> dict[str, Any]:
        by_cat = {cat: 0 for cat in sorted(ConnectorCategory.ALL)}
        for c in self._connectors.values():
            by_cat[c.category] = by_cat.get(c.category, 0) + 1
        return {"connectors": len(self._connectors), "by_category": by_cat,
                "capabilities": len(self.capabilities()),
                "unhealthy": len(self.health()["unhealthy"])}


__all__ = ["ConnectorRegistry"]
