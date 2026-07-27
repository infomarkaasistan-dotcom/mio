"""MIO Core · MCP Kataloğu — bilinen (gerçek) MCP sunucularının hazır tanımları.

Kullanıcı direktifi: "Tüm MCP'leri kur; ben yalnız API/yetki bağlama kısımlarını yapayım." Bu katalog, resmi
Model Context Protocol sunucularını (ve yaygın toplulukları) MIO'ya **tanım olarak** getirir. Açılışta hepsi
`mcp_management`'e **UNTRUSTED** kaydedilir (Anayasa Madde 24: güven + etkinleştirme kullanıcıya aittir). Kullanıcı
arayüzden birini seçer, gerekli API anahtarını girer ve yetki (trust) verir → o zaman etkinleşir.

**Dürüstlük:** Buradaki komut/paket adları gerçektir (npmjs `@modelcontextprotocol/*`). Bir sunucunun fiilen
ÇALIŞMASI için hedef makinede Node/npx (stdio sunucuları) + ilgili API anahtarı gerekir — bunları kullanıcı sağlar.
Katalog bunları "kurar" (kaydeder + neyin gerektiğini bildirir); sahte çalışma taklidi YAPMAZ (Madde 8).

Her giriş: key · name · command (çalıştırma) · transport · env (gerekli anahtarlar) · category · risk · description.
"""

from __future__ import annotations

from typing import Any

# risk: low (okuma/yerel) · medium (dış veri/yazma) · high (geri-alınamaz/gizli/yetkili erişim)
MCP_CATALOG: list[dict[str, Any]] = [
    # -- Yerel / temel (anahtar gerektirmez) --
    {"key": "filesystem", "name": "Filesystem", "command": "npx -y @modelcontextprotocol/server-filesystem",
     "transport": "stdio", "env": [], "category": "system", "risk": "medium",
     "description": "Yerel dosya okuma/yazma (izin verilen klasörler)."},
    {"key": "memory", "name": "Memory (Knowledge Graph)", "command": "npx -y @modelcontextprotocol/server-memory",
     "transport": "stdio", "env": [], "category": "knowledge", "risk": "low",
     "description": "Kalıcı bilgi grafiği belleği."},
    {"key": "fetch", "name": "Web Fetch", "command": "npx -y @modelcontextprotocol/server-fetch",
     "transport": "stdio", "env": [], "category": "web", "risk": "low",
     "description": "Web sayfası getir ve içerik çıkar."},
    {"key": "sequential-thinking", "name": "Sequential Thinking",
     "command": "npx -y @modelcontextprotocol/server-sequential-thinking",
     "transport": "stdio", "env": [], "category": "reasoning", "risk": "low",
     "description": "Adım adım yapılandırılmış akıl yürütme."},
    {"key": "time", "name": "Time", "command": "npx -y @modelcontextprotocol/server-time",
     "transport": "stdio", "env": [], "category": "system", "risk": "low",
     "description": "Saat dilimi / zaman dönüşümleri."},
    {"key": "sqlite", "name": "SQLite", "command": "npx -y @modelcontextprotocol/server-sqlite",
     "transport": "stdio", "env": [], "category": "data", "risk": "medium",
     "description": "Yerel SQLite veritabanı sorgula."},
    {"key": "git", "name": "Git", "command": "npx -y @modelcontextprotocol/server-git",
     "transport": "stdio", "env": [], "category": "system", "risk": "medium",
     "description": "Yerel git deposu işlemleri."},
    {"key": "puppeteer", "name": "Puppeteer (Tarayıcı)", "command": "npx -y @modelcontextprotocol/server-puppeteer",
     "transport": "stdio", "env": [], "category": "web", "risk": "high",
     "description": "Tarayıcı otomasyonu (gezinme, tıklama, ekran görüntüsü)."},

    # -- API anahtarı gerektiren (kullanıcı girer) --
    {"key": "github", "name": "GitHub", "command": "npx -y @modelcontextprotocol/server-github",
     "transport": "stdio", "env": ["GITHUB_PERSONAL_ACCESS_TOKEN"], "category": "system", "risk": "high",
     "description": "GitHub depo/issue/PR yönetimi."},
    {"key": "brave-search", "name": "Brave Search", "command": "npx -y @modelcontextprotocol/server-brave-search",
     "transport": "stdio", "env": ["BRAVE_API_KEY"], "category": "web", "risk": "low",
     "description": "Web araması (Brave)."},
    {"key": "google-maps", "name": "Google Maps", "command": "npx -y @modelcontextprotocol/server-google-maps",
     "transport": "stdio", "env": ["GOOGLE_MAPS_API_KEY"], "category": "web", "risk": "low",
     "description": "Konum, yol tarifi, yer arama."},
    {"key": "slack", "name": "Slack", "command": "npx -y @modelcontextprotocol/server-slack",
     "transport": "stdio", "env": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"], "category": "communication", "risk": "high",
     "description": "Slack mesaj gönder/oku, kanal yönet."},
    {"key": "google-drive", "name": "Google Drive", "command": "npx -y @modelcontextprotocol/server-gdrive",
     "transport": "stdio", "env": ["GDRIVE_CREDENTIALS_PATH"], "category": "productivity", "risk": "high",
     "description": "Drive dosya ara/oku."},
    {"key": "postgres", "name": "PostgreSQL", "command": "npx -y @modelcontextprotocol/server-postgres",
     "transport": "stdio", "env": ["POSTGRES_CONNECTION_STRING"], "category": "data", "risk": "high",
     "description": "PostgreSQL sorgula (salt-okunur)."},
    {"key": "notion", "name": "Notion", "command": "npx -y @notionhq/notion-mcp-server",
     "transport": "stdio", "env": ["NOTION_API_KEY"], "category": "productivity", "risk": "medium",
     "description": "Notion sayfa/veritabanı."},
    {"key": "sentry", "name": "Sentry", "command": "npx -y @modelcontextprotocol/server-sentry",
     "transport": "stdio", "env": ["SENTRY_AUTH_TOKEN"], "category": "system", "risk": "medium",
     "description": "Sentry hata/issue analizi."},
]

_BY_KEY = {e["key"]: e for e in MCP_CATALOG}


def get(key: str) -> dict[str, Any] | None:
    return _BY_KEY.get(key)


def install_catalog(mio, *, actor: str = "owner") -> dict[str, Any]:
    """Katalogdaki tüm MCP sunucularını `mcp_management`'e UNTRUSTED kaydeder (idempotent).

    Zaten kayıtlıysa atlar (ada göre). Güven/etkinleştirme YAPMAZ — Madde 24 gereği kullanıcıya bırakır.
    Dönüş: {registered:[...], skipped:[...], total}."""
    existing = {s.get("name") for s in mio.mcp_management.list_servers(actor)}
    registered, skipped = [], []
    for e in MCP_CATALOG:
        if e["name"] in existing:
            skipped.append(e["key"])
            continue
        try:
            mio.mcp_management.register_server(
                actor, e["name"], url=e.get("command", ""), transport=e.get("transport", "stdio"),
                version="catalog", sandboxed=True)   # UNTRUSTED (varsayılan) — kullanıcı yetki verir
            registered.append(e["key"])
        except Exception as exc:  # noqa: BLE001 — bir giriş kaydedilemezse diğerleri sürer (görünür)
            skipped.append(f"{e['key']} (hata: {type(exc).__name__})")
    return {"registered": registered, "skipped": skipped, "total": len(MCP_CATALOG)}


def catalog_status(mio, *, actor: str = "owner") -> list[dict[str, Any]]:
    """Katalog + canlı kayıt durumu birleşik (arayüz için). Her giriş: tanım + registered/trust/enabled."""
    live = {s.get("name"): s for s in mio.mcp_management.list_servers(actor)}
    out = []
    for e in MCP_CATALOG:
        s = live.get(e["name"], {})
        out.append({**e, "registered": bool(s),
                    "trust_level": s.get("trust_level"), "enabled": s.get("enabled", False),
                    "server_id": s.get("id"), "needs_keys": e["env"]})
    return out


__all__ = ["MCP_CATALOG", "get", "install_catalog", "catalog_status"]
