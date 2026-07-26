"""MIO Core · Capability Management Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Çekirdek `CapabilityRegistry`'yi (Born Capable in-memory aggregate) SARAN governance kabuğu (Madde 15/16):
maturity yaşam-döngüsü (Governance Extensions §7), sürümlü sözleşme (Madde 29), yetenek seçimi ve evolution
denetimi (Madde 26). Çekirdek yeniden kullanılır; kopyalanmaz."""

from __future__ import annotations

from dataclasses import dataclass, field

# Çekirdek yetenek yapıları yeniden kullanılır.
from mio_core.capability import Capability, CapabilityRegistry, MaturityLevel, RiskLevel, infer_category

__all__ = [
    "Capability", "CapabilityRegistry", "MaturityLevel", "RiskLevel", "infer_category",
    "VALID_MATURITY_TRANSITIONS", "CapabilityConfig",
    "CapabilityMgmtError", "ValidationError", "UnauthorizedError", "NotFoundError",
]

# Governance Extensions §7 — geçerli maturity geçişleri (ileri + deprecate/retire). Terminal: retired.
VALID_MATURITY_TRANSITIONS: dict[str, set[str]] = {
    MaturityLevel.EXPERIMENTAL: {MaturityLevel.PREVIEW, MaturityLevel.DEPRECATED, MaturityLevel.RETIRED},
    MaturityLevel.PREVIEW: {MaturityLevel.STABLE, MaturityLevel.DEPRECATED, MaturityLevel.RETIRED},
    MaturityLevel.STABLE: {MaturityLevel.PRODUCTION, MaturityLevel.DEPRECATED, MaturityLevel.RETIRED},
    MaturityLevel.PRODUCTION: {MaturityLevel.DEPRECATED, MaturityLevel.RETIRED},
    MaturityLevel.DEPRECATED: {MaturityLevel.RETIRED},
    MaturityLevel.RETIRED: set(),
}


class CapabilityMgmtError(Exception):
    """Capability Management Domain temel hatası."""


class ValidationError(CapabilityMgmtError):
    pass


class UnauthorizedError(CapabilityMgmtError):
    pass


class NotFoundError(CapabilityMgmtError):
    pass


@dataclass
class CapabilityConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Planning", "Reasoning", "Engineering", "Workflow"})
    admin_actors: set = field(default_factory=lambda: {"owner", "Executive", "Operations"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_admin(self, actor: str) -> bool:
        return actor == "owner" or actor in self.admin_actors
