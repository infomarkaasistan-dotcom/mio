"""MIO Core · Capability Marketplace + Recommendation + Auto Installer (Öncelik 5, 7, 4), LLM-BAĞIMSIZ.

Marketplace: kurulabilir MCP'lerin kataloğu (Executive buradan seçer). Recommendation: görev/kategori için
eksik yeteneği fark edip önerir. Auto Installer: MIO eksik capability'yi kendisi fark eder → risk/trust →
kullanıcı onayı → kurulum (enjekte adaptör) → discovery → Executive'e rapor → Brain kullanır. Hepsi
deterministik; gerçek kurulum enjekte edilir (yoksa dürüstçe 'installer yok')."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from mio_core.capability import CapabilityRegistry, RiskLevel
from mio_core.events import Ev

__all__ = ["MarketEntry", "CapabilityMarketplace", "RecommendationEngine", "AutoInstaller",
           "InstallResult", "default_marketplace"]


@dataclass
class MarketEntry:
    name: str
    description: str = ""
    category: str = "general"
    transport: str = "stdio"
    command: list[str] = field(default_factory=list)
    url: str = ""
    official: bool = True
    trust_base: int = 60
    risk: str = RiskLevel.MEDIUM
    license: str = ""
    requires_key: bool = False

    def to_dict(self):
        return {"name": self.name, "description": self.description, "category": self.category,
                "transport": self.transport, "official": self.official, "trust_base": self.trust_base,
                "risk": self.risk, "license": self.license, "requires_key": self.requires_key}


class CapabilityMarketplace:
    def __init__(self) -> None:
        self._entries: dict[str, MarketEntry] = {}

    def add(self, e: MarketEntry) -> MarketEntry:
        self._entries[e.name] = e
        return e

    def add_all(self, entries: list[MarketEntry]) -> int:
        for e in entries:
            self.add(e)
        return len(entries)

    def get(self, name: str) -> Optional[MarketEntry]:
        return self._entries.get(name)

    def list(self, category: Optional[str] = None) -> list[MarketEntry]:
        return [e for e in self._entries.values() if category is None or e.category == category]

    def search(self, query: str) -> list[MarketEntry]:
        kws = [w.lower() for w in query.split() if len(w) > 2]
        out = []
        for e in self._entries.values():
            hay = (e.name + " " + e.description + " " + e.category).lower()
            score = sum(1 for k in kws if k in hay)
            if score:
                out.append((score, e))
        out.sort(key=lambda t: (t[0], t[1].trust_base), reverse=True)
        return [e for _, e in out]

    def installed(self, capabilities: CapabilityRegistry) -> set[str]:
        return {c.provenance for c in capabilities.list() if c.provenance}


class RecommendationEngine:
    """Eksik yeteneği fark edip Marketplace'ten önerir; Executive'e rapor eder."""

    def __init__(self, marketplace: CapabilityMarketplace, capabilities: CapabilityRegistry, *,
                 bus=None) -> None:
        self._market = marketplace
        self._caps = capabilities
        self._bus = bus

    def _connected_categories(self) -> set[str]:
        return {c.category for c in self._caps.list() if c.connected}

    def recommend_for_category(self, category: str) -> list[MarketEntry]:
        if category in self._connected_categories():
            return []                             # zaten var
        recs = [e for e in self._market.list(category)
                if e.name not in self._market.installed(self._caps)]
        if recs and self._bus:
            self._bus.publish(Ev.RECOMMENDATION, {"category": category, "options": [e.name for e in recs]})
        return recs

    def recommend(self, query: str) -> list[MarketEntry]:
        installed = self._market.installed(self._caps)
        recs = [e for e in self._market.search(query) if e.name not in installed]
        if recs and self._bus:
            self._bus.publish(Ev.RECOMMENDATION, {"query": query, "options": [e.name for e in recs]})
        return recs


# Kurulumu GERÇEKTEN yapan adaptör: MarketEntry → bağlanılabilir MCPServerConfig (yoksa None/exception).
Installer = Callable[[MarketEntry], "object"]


@dataclass
class InstallResult:
    name: str
    status: str                                  # installed | needs_approval | not_found | no_installer | failed
    capabilities: int = 0
    reason: str = ""


class AutoInstaller:
    """MIO eksik capability'yi kendisi kurabilir: risk/trust → onay → kurulum → discovery → Executive rapor."""

    def __init__(self, marketplace: CapabilityMarketplace, discovery, *,
                 installer: Optional[Installer] = None, client_factory: Optional[Callable] = None,
                 bus=None) -> None:
        self._market = marketplace
        self._discovery = discovery
        self._installer = installer
        self._client_factory = client_factory
        self._bus = bus

    def install(self, name: str, *, user_approved: bool = False) -> InstallResult:
        entry = self._market.get(name)
        if entry is None:
            return InstallResult(name, "not_found", reason="Marketplace'te yok")
        if (entry.risk == RiskLevel.HIGH or entry.requires_key) and not user_approved:
            return InstallResult(name, "needs_approval",
                                 reason="Kurulum için kullanıcı onayı gerekiyor (risk/anahtar).")
        if self._installer is None:
            return InstallResult(name, "no_installer", reason="Kurulum adaptörü bağlı değil (dürüst).")
        try:
            config = self._installer(entry)       # GERÇEK kurulum → bağlanılabilir config
            if self._client_factory is not None:
                client = self._client_factory([config])
            else:
                from mio_core.adapters.mcp_client import StdioMCPClient
                client = StdioMCPClient([config])
            report = self._discovery.discover(client)
        except Exception as e:  # noqa: BLE001
            return InstallResult(name, "failed", reason=str(e)[:200])
        if self._bus:
            self._bus.publish(Ev.INSTALL, {"name": name, "capabilities": len(report.capabilities)})
        return InstallResult(name, "installed", capabilities=len(report.capabilities))


def default_marketplace() -> list[MarketEntry]:
    """Bilinen MCP'lerin başlangıç kataloğu (öncelikli kategoriler). Purpose'a göre ücretsiz/yerel önce."""
    npx = lambda *a: ["npx", "-y", *a]  # noqa: E731
    uvx = lambda *a: ["uvx", *a]        # noqa: E731
    return [
        MarketEntry("filesystem", "Yerel dosya", "filesystem", command=npx("@modelcontextprotocol/server-filesystem"), trust_base=90, license="MIT"),
        MarketEntry("git", "Yerel git", "vcs", command=uvx("mcp-server-git"), trust_base=85, license="MIT"),
        MarketEntry("github", "GitHub repo/issue", "vcs", command=npx("@modelcontextprotocol/server-github"), trust_base=88, requires_key=True, license="MIT"),
        MarketEntry("fetch", "Web çek", "web_search", command=uvx("mcp-server-fetch"), risk=RiskLevel.LOW, trust_base=80, license="MIT"),
        MarketEntry("memory", "Bilgi grafı hafıza", "general", command=npx("@modelcontextprotocol/server-memory"), risk=RiskLevel.LOW, trust_base=80, license="MIT"),
        MarketEntry("sequential-thinking", "Adımlı muhakeme", "general", command=npx("@modelcontextprotocol/server-sequential-thinking"), risk=RiskLevel.LOW, trust_base=80, license="MIT"),
        MarketEntry("playwright", "Tarayıcı otomasyon", "browser_automation", command=npx("@playwright/mcp"), risk=RiskLevel.HIGH, trust_base=82, license="Apache-2.0"),
        MarketEntry("postgres", "PostgreSQL", "database", command=npx("@modelcontextprotocol/server-postgres"), trust_base=75, license="MIT"),
        MarketEntry("brave-search", "Web arama", "web_search", command=npx("@modelcontextprotocol/server-brave-search"), requires_key=True, trust_base=75, license="MIT"),
        MarketEntry("slack", "Slack mesaj", "messaging", command=npx("@modelcontextprotocol/server-slack"), requires_key=True, trust_base=75, license="MIT"),
        MarketEntry("stripe", "Ödeme/fatura", "payment", command=npx("@stripe/mcp"), risk=RiskLevel.HIGH, requires_key=True, trust_base=85, license="MIT"),
        MarketEntry("notion", "Notion", "productivity", command=npx("@notionhq/notion-mcp-server"), requires_key=True, trust_base=80, license="MIT"),
    ]
