"""MIO Core · Capability Registry — SEMANTİK yetenek modeli (ADR-0002 Madde 6), LLM-BAĞIMSIZ.

Capability yalnız bir isim değildir; kendi semantiğini taşır: ne yapabilir/yapamaz, risk, gereken izinler,
hangi Brain kullanabilir, maliyet, kullanıcı onayı, alternatif, öncelik. Böylece Executive GERÇEKTEN karar
verebilir ("bu işi hangi araçla, hangi riskle, hangi izinle yaparım?").

Born Capable: MIO yetenek TANIMLARIYLA doğar (neleri yapabilirim/yapamam bilgisi). Bir yeteneğin O AN
BAĞLI olup olmadığı (connected) kurulumda keşfedilir (MCP discovery / health check). "Bağlı değil" dürüsttür.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = ["RiskLevel", "MaturityLevel", "Capability", "CapabilityRegistry", "infer_category"]


class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MaturityLevel:
    """Governance Extensions §7 — Executive seçimde gözetir."""
    EXPERIMENTAL = "experimental"
    PREVIEW = "preview"
    STABLE = "stable"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    RETIRED = "retired"

    ORDER = {EXPERIMENTAL: 1, PREVIEW: 2, STABLE: 3, PRODUCTION: 4, DEPRECATED: 0, RETIRED: -1}
    USABLE = {EXPERIMENTAL, PREVIEW, STABLE, PRODUCTION}


# Yetenek adından semantik kategori (alternatifleri gruplamak → Capability Graph + Load Balancer).
_CATEGORY_HINTS = {
    "browser_automation": ("browser", "playwright", "puppeteer", "chrome", "screenshot", "navigate", "page"),
    "database": ("sql", "postgres", "sqlite", "mysql", "mongo", "query", "database", "db"),
    "vcs": ("git", "github", "gitlab", "commit", "push", "pull", "repo", "branch"),
    "filesystem": ("file", "directory", "folder", "path", "read_file", "write_file"),
    "web_search": ("search", "brave", "exa", "web", "fetch", "crawl", "firecrawl"),
    "llm": ("llm", "generate", "completion", "chat", "embed"),
    "messaging": ("slack", "discord", "telegram", "email", "gmail", "message", "send"),
    "media": ("ffmpeg", "video", "audio", "image", "ocr", "whisper", "tts", "speech"),
    "payment": ("payment", "stripe", "invoice", "charge", "pay"),
}


def infer_category(name: str, *, default: str = "general") -> str:
    low = name.lower()
    for category, hints in _CATEGORY_HINTS.items():
        if any(h in low for h in hints):
            return category
    return default


@dataclass
class Capability:
    name: str
    description: str = ""
    can_do: list[str] = field(default_factory=list)
    cannot_do: list[str] = field(default_factory=list)
    risk_level: str = RiskLevel.LOW
    required_permissions: list[str] = field(default_factory=list)
    usable_by_brains: list[str] = field(default_factory=lambda: ["*"])   # ["*"] = tüm Brain'ler
    incurs_cost: bool = False
    requires_user_approval: bool = False
    alternatives: list[str] = field(default_factory=list)
    priority: int = 50                                                   # 0..100 (yüksek = tercih edilir)
    source: str = "native"                                              # native | mcp | tool
    connected: bool = False                                             # kurulumda keşfedilir (dürüst)
    parameters: dict[str, Any] = field(default_factory=dict)            # manifest (MCP inputSchema) → nasıl çağrılır
    provenance: str = ""                                                # nereden geldi (MCP sunucu adı vb.)
    category: str = "general"                                          # semantik grup (alternatifler/load-balance için)
    maturity: str = MaturityLevel.STABLE                               # Governance §7 (experimental..retired)
    contract_version: str = "1.0.0"                                    # Platform Invariant: sözleşme versiyonlu

    def usable_by(self, brain: str) -> bool:
        return "*" in self.usable_by_brains or brain in self.usable_by_brains

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "can_do": list(self.can_do),
                "cannot_do": list(self.cannot_do), "risk_level": self.risk_level,
                "required_permissions": list(self.required_permissions),
                "usable_by_brains": list(self.usable_by_brains), "incurs_cost": self.incurs_cost,
                "requires_user_approval": self.requires_user_approval,
                "alternatives": list(self.alternatives), "priority": self.priority,
                "source": self.source, "connected": self.connected,
                "parameters": dict(self.parameters), "provenance": self.provenance,
                "category": self.category, "maturity": self.maturity,
                "contract_version": self.contract_version}


class CapabilityRegistry:
    """Yetenek kayıt defteri (bellek-içi; her doğuşta innate tanımlarla dolar, keşifle güncellenir)."""

    def __init__(self) -> None:
        self._caps: dict[str, Capability] = {}

    def register(self, capability: Capability) -> Capability:
        self._caps[capability.name] = capability
        return capability

    def register_all(self, capabilities: list[Capability]) -> int:
        for c in capabilities:
            self.register(c)
        return len(capabilities)

    def get(self, name: str) -> Optional[Capability]:
        return self._caps.get(name)

    def set_connected(self, name: str, connected: bool) -> Optional[Capability]:
        """Kurulum keşfi: bir yeteneğin bağlı olup olmadığını işaretler."""
        c = self._caps.get(name)
        if c is not None:
            c.connected = connected
        return c

    def list(self) -> list[Capability]:
        return list(self._caps.values())

    def list_connected(self) -> list[Capability]:
        return [c for c in self._caps.values() if c.connected]

    def list_disconnected(self) -> list[Capability]:
        return [c for c in self._caps.values() if not c.connected]

    def list_for_brain(self, brain: str, *, only_connected: bool = True) -> list[Capability]:
        return [c for c in self._caps.values()
                if c.usable_by(brain) and (c.connected or not only_connected)]

    def can(self, name: str) -> bool:
        """Bu yeteneğe ŞU AN sahip miyim (tanımlı VE bağlı)?"""
        c = self._caps.get(name)
        return bool(c and c.connected)

    def names(self) -> list[str]:
        return list(self._caps.keys())
