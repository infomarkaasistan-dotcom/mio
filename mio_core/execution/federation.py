"""MIO Core · Federation (Öncelik 11) — MİMARİ-HAZIR, minimal. LLM-BAĞIMSIZ.

Birden fazla MIO (Desktop/Server/Mobile/Cloud) ileride capability paylaşabilmeli. Bugün UZAK bağlantı
IMPLEMENTE EDİLMEZ; yalnız mimari buna açık olsun: capability'ler bir `CapabilityProvider` arkasından gelir;
`FederatedCapabilities` yerel + (ileride) uzak sağlayıcıları birleştirir. Uzak sağlayıcı bir adaptör olur,
çekirdek değişmez."""

from __future__ import annotations

from typing import Protocol

from mio_core.capability import Capability, CapabilityRegistry

__all__ = ["CapabilityProvider", "LocalProvider", "FederatedCapabilities"]


class CapabilityProvider(Protocol):
    """Bir capability kaynağı (yerel registry, uzak MIO, bulut...). Uzak olanlar ileride adaptördür."""
    def node(self) -> str: ...
    def list_capabilities(self) -> list[Capability]: ...


class LocalProvider:
    def __init__(self, registry: CapabilityRegistry, *, node: str = "local") -> None:
        self._reg = registry
        self._node = node

    def node(self) -> str:
        return self._node

    def list_capabilities(self) -> list[Capability]:
        return self._reg.list()


class FederatedCapabilities:
    """Birden fazla düğümün yeteneklerini birleştirir (bugün yalnız yerel; uzak eklenince kod değişmez)."""

    def __init__(self) -> None:
        self._providers: list[CapabilityProvider] = []

    def add_provider(self, provider: CapabilityProvider) -> None:
        self._providers.append(provider)

    def all(self) -> list[dict]:
        out = []
        for p in self._providers:
            for c in p.list_capabilities():
                out.append({"node": p.node(), "name": c.name, "category": c.category,
                            "connected": c.connected, "risk": c.risk_level})
        return out

    def find(self, capability_name: str) -> list[dict]:
        """Bir yeteneği HANGİ düğümlerin sağladığı (federasyon load-balance temeli)."""
        return [r for r in self.all() if r["name"] == capability_name]

    def nodes(self) -> list[str]:
        return [p.node() for p in self._providers]
