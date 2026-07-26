"""MIO Core · MCP Management Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class MCPEvents:
    REGISTERED = "mcp.registered"
    DISCOVERED = "mcp.discovered"
    HEALTH_CHECKED = "mcp.health_checked"
    TRUST_CHANGED = "mcp.trust_changed"
    ACTIVATED = "mcp.activated"
    REMOVED = "mcp.removed"


OPERATIONS = ("register_server", "discover", "health_check", "set_trust", "activate", "remove_server",
              "describe", "list_servers", "lifecycle_history", "stats")


def mcp_mgmt_contract() -> dict[str, Any]:
    return {
        "domain": "mcp_management",
        "version": CONTRACT_VERSION,
        "description": "Çekirdek MCPHub'ı saran governance: MCP sunucu yaşam-döngüsü + TRUST governance "
                       "(Madde 24) + sağlık + kalıcı kayıt. LLM-bağımsız; çekirdek değiştirilmez.",
        "operations": list(OPERATIONS),
        "events": [MCPEvents.REGISTERED, MCPEvents.DISCOVERED, MCPEvents.HEALTH_CHECKED,
                   MCPEvents.TRUST_CHANGED, MCPEvents.ACTIVATED, MCPEvents.REMOVED],
        "trust_levels": ["untrusted", "trusted", "verified"],
        "server_statuses": ["unknown", "healthy", "degraded", "down"],
        "invariants": ["untrusted sunucu yalnız sandbox + açık onayla aktive edilir (Madde 24)",
                       "trust değişimi admin yetkisi ister ve denetlenir",
                       "sunucu kaydı kalıcıdır (restart'ta hub'a geri yüklenir)",
                       "çekirdek MCPHub sarılır, değiştirilmez (Madde 15/16)"],
    }
