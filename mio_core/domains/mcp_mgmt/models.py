"""MIO Core · MCP Management Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Çekirdek `MCPHub`'ı (+ Meta metrikleri) SARAN governance kabuğu (Madde 15/16): MCP sunucu yaşam-döngüsü,
TRUST governance (Madde 24 — untrusted sunucu sandbox'lanır, aktivasyon kapılı), sağlık ve kalıcı kayıt.
Çekirdek MCP yapıları yeniden kullanılır; kopyalanmaz."""

from __future__ import annotations

from dataclasses import dataclass, field

# Çekirdek MCP yapıları yeniden kullanılır.
from mio_core.execution.mcp_hub import MCPHub, MCPServer, MCPTool, ServerStatus, TrustLevel

__all__ = [
    "MCPHub", "MCPServer", "MCPTool", "ServerStatus", "TrustLevel",
    "TRUST_ORDER", "ACTIVATABLE_TRUST", "MCPMgmtConfig",
    "MCPMgmtError", "ValidationError", "UnauthorizedError", "NotFoundError", "TrustError",
]

# Trust sıralaması (yüksek = daha güvenilir). untrusted < trusted < verified.
TRUST_ORDER = {TrustLevel.UNTRUSTED: 0, TrustLevel.TRUSTED: 1, TrustLevel.VERIFIED: 2}
# Aktivasyon için gereken minimum trust (untrusted YALNIZ sandbox'ta ve açık onayla).
ACTIVATABLE_TRUST = {TrustLevel.TRUSTED, TrustLevel.VERIFIED}
VALID_TRANSPORTS = {"stdio", "http", "sse"}


class MCPMgmtError(Exception):
    """MCP Management Domain temel hatası."""


class ValidationError(MCPMgmtError):
    pass


class UnauthorizedError(MCPMgmtError):
    pass


class NotFoundError(MCPMgmtError):
    pass


class TrustError(MCPMgmtError):
    """Trust politikası ihlali (ör. güvenilmeyen sunucuyu sandbox'suz aktive etme)."""


@dataclass
class MCPMgmtConfig:
    require_trust_for_activation: bool = True     # Madde 24: untrusted → yalnız sandbox + açık onay
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Security", "Engineering", "Workflow"})
    admin_actors: set = field(default_factory=lambda: {"owner", "Executive", "Operations", "Security"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_admin(self, actor: str) -> bool:
        return actor == "owner" or actor in self.admin_actors
