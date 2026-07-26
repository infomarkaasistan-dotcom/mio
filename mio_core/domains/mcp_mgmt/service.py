"""MIO Core · MCP Management Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Çekirdek `MCPHub`'ı SARAR (Madde 15/16 — çekirdek yeniden yazılmaz). MCP sunucu yaşam-döngüsü + TRUST
governance (Madde 24) + sağlık + kalıcı kayıt. Not: yürütme-zamanı trust kapısı zaten çekirdekte
(`map_and_bind`: untrusted+riskli araç → kullanıcı onayı); bu domain trust yaşam-döngüsünü, kalıcılığı ve
denetimi ekler. authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contract import CONTRACT_VERSION, MCPEvents, mcp_mgmt_contract
from .models import (
    ACTIVATABLE_TRUST,
    MCPHub,
    MCPMgmtConfig,
    MCPServer,
    NotFoundError,
    ServerStatus,
    TRUST_ORDER,
    TrustLevel,
    UnauthorizedError,
    VALID_TRANSPORTS,
    ValidationError,
)
from .repository import MCPRepository

logger = logging.getLogger("mio.domain.mcp_mgmt")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MCPManagementDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, hub: MCPHub, repository: MCPRepository, *, capabilities=None, orchestrator=None,
                 meta=None, bus=None, config: Optional[MCPMgmtConfig] = None) -> None:
        self._hub = hub
        self._repo = repository
        self._caps = capabilities         # aktivasyon için CapabilityRegistry
        self._orch = orchestrator         # aktivasyon için ToolOrchestrator
        self._meta = meta                 # opsiyonel Meta MCP metrikleri
        self._bus = bus
        self._cfg = config or MCPMgmtConfig()
        self._metrics = {"registered": 0, "discoveries": 0, "trust_changes": 0, "activations": 0}

    # ------------------------------------------------------------------ #
    def restore(self, actor: str) -> dict[str, Any]:
        """Kalıcı sunucu kaydını in-memory hub'a geri yükler (boot'ta). Araçlar discover'da yeniden dolar."""
        self._authorize_admin(actor)
        applied = 0
        for d in self._repo.all_servers():
            if self._hub.get_server(d["id"]) is None:
                self._hub.register_server(self._server_from_dict(d))
                applied += 1
        return {"applied": applied}

    def register_server(self, actor: str, name: str, *, url: str = "", transport: str = "stdio",
                        trust_level: str = TrustLevel.UNTRUSTED, version: str = "",
                        sandboxed: bool = True) -> dict[str, Any]:
        self._authorize_admin(actor)
        name = self._require(name, "sunucu adı")
        if transport not in VALID_TRANSPORTS:
            raise ValidationError(f"Geçersiz transport: {transport} (izinli: {sorted(VALID_TRANSPORTS)})")
        if trust_level not in TRUST_ORDER:
            raise ValidationError(f"Geçersiz trust seviyesi: {trust_level}")
        server = MCPServer(name=name, url=url, version=version, transport=transport,
                           trust_level=trust_level, sandboxed=bool(sandboxed))
        self._hub.register_server(server)
        self._persist(server, "registered", f"transport={transport} trust={trust_level}")
        self._metrics["registered"] += 1
        self._emit(MCPEvents.REGISTERED, {"actor": actor, "server_id": server.id, "name": name,
                                          "trust": trust_level})
        return server.to_dict()

    def discover(self, actor: str) -> dict[str, Any]:
        """İstemciyle sunucuları/araçları keşfeder. İstemci yoksa 0 (dürüst)."""
        self._authorize_admin(actor)
        count = self._hub.discover()
        for s in self._hub.list_servers():
            self._persist(s, "discovered", f"tools={len(s.tools)}")
        self._metrics["discoveries"] += 1
        self._emit(MCPEvents.DISCOVERED, {"actor": actor, "servers": count})
        return {"discovered": count, "servers": len(self._hub.list_servers())}

    def health_check(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        result = self._hub.health_check()
        for s in self._hub.list_servers():
            self._repo.put_server(s.to_dict(), _now())
        self._emit(MCPEvents.HEALTH_CHECKED, {"actor": actor, "servers": len(result)})
        return result

    def set_trust(self, actor: str, server_id: str, trust_level: str) -> dict[str, Any]:
        """Trust yaşam-döngüsü (Madde 24). Admin yetkisi + denetim. Yürütme kapısı map_and_bind'te uygulanır."""
        self._authorize_admin(actor)
        if trust_level not in TRUST_ORDER:
            raise ValidationError(f"Geçersiz trust seviyesi: {trust_level}")
        server = self._require_server(server_id)
        prev, server.trust_level = server.trust_level, trust_level
        self._persist(server, "trust_changed", f"{prev}→{trust_level} by {actor}")
        self._metrics["trust_changes"] += 1
        self._emit(MCPEvents.TRUST_CHANGED, {"server_id": server_id, "from": prev, "to": trust_level})
        return server.to_dict()

    def activate(self, actor: str) -> dict[str, Any]:
        """Sağlıklı sunucuların araçlarını Capability+executor olarak bağlar (hub'a delege). Trust kapısı:
        untrusted sunucuların riskli araçları yürütmede kullanıcı onayı ister (çekirdek map_and_bind)."""
        self._authorize_admin(actor)
        if self._caps is None or self._orch is None:
            raise ValidationError("Aktivasyon için CapabilityRegistry + ToolOrchestrator bağlı olmalı")
        report = self._hub.activate(self._caps, self._orch)
        for s in self._hub.list_servers():
            self._repo.put_server(s.to_dict(), _now())
        untrusted = [s.name for s in self._hub.list_servers()
                     if s.trust_level not in ACTIVATABLE_TRUST and s.status == ServerStatus.HEALTHY]
        report["trust_gated_servers"] = untrusted    # bunların riskli araçları onay ister (Madde 24)
        self._metrics["activations"] += 1
        self._emit(MCPEvents.ACTIVATED, {"actor": actor, "bound": report.get("bound_capabilities", 0),
                                         "trust_gated": len(untrusted)})
        return report

    def remove_server(self, actor: str, server_id: str) -> None:
        self._authorize_admin(actor)
        self._require_server(server_id)
        self._hub.remove_server(server_id)
        self._repo.delete_server(server_id)
        self._repo.append_lifecycle(server_id, "removed", f"by {actor}", _now())
        self._emit(MCPEvents.REMOVED, {"actor": actor, "server_id": server_id})

    # ------------------------------------------------------------------ #
    def describe(self, actor: str, server_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_server(server_id).to_dict()

    def list_servers(self, actor: str, *, trust_level: Optional[str] = None,
                     status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        out = self._hub.list_servers()
        if trust_level is not None:
            out = [s for s in out if s.trust_level == trust_level]
        if status is not None:
            out = [s for s in out if s.status == status]
        return [s.to_dict() for s in out]

    def lifecycle_history(self, actor: str, *, server: Optional[str] = None,
                          limit: int = 100) -> list[dict[str, Any]]:
        self._authorize(actor)
        return self._repo.lifecycle_recent(min(int(limit), 500), server=server)

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        servers = self._hub.list_servers()
        by_trust = {t: 0 for t in TRUST_ORDER}
        by_status = {}
        for s in servers:
            by_trust[s.trust_level] = by_trust.get(s.trust_level, 0) + 1
            by_status[s.status] = by_status.get(s.status, 0) + 1
        return {"servers": len(servers), "persisted": self._repo.count_servers(),
                "by_trust": by_trust, "by_status": by_status,
                "healthy": by_status.get(ServerStatus.HEALTHY, 0),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return mcp_mgmt_contract()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _server_from_dict(d: dict) -> MCPServer:
        return MCPServer(name=d["name"], url=d.get("url", ""), version=d.get("version", ""),
                         transport=d.get("transport", "stdio"),
                         trust_level=d.get("trust_level", TrustLevel.UNTRUSTED),
                         sandboxed=bool(d.get("sandboxed", True)),
                         status=d.get("status", ServerStatus.UNKNOWN), id=d["id"])

    def _persist(self, server: MCPServer, kind: str, detail: str) -> None:
        self._repo.put_server(server.to_dict(), _now())
        self._repo.append_lifecycle(server.id, kind, detail, _now())

    def _require_server(self, server_id: str) -> MCPServer:
        server = self._hub.get_server(server_id)
        if server is None:
            raise NotFoundError(f"MCP sunucusu bulunamadı: {server_id}")
        return server

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' MCP erişimi için yetkili değil")

    def _authorize_admin(self, actor: str) -> None:
        if not self._cfg.is_admin(actor):
            raise UnauthorizedError(f"'{actor}' MCP yönetimi için yetkili değil (admin gerekir)")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
