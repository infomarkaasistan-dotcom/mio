# MCP Management Domain (Constitution Faz 2 · Domain 17) — Maturity: STABLE

> Constitution refs: Madde 15 (Evolutionary — sar, yeniden yazma), Madde 16 (küçük çekirdek), Madde 24
> (MCP Trust Validation), Governance Extensions §6 (Lifecycle). **Compliance: FULLY COMPLIANT (kapsam içi).**

Çekirdek `MCPHub`'ı **saran** governance kabuğu. MCP sunucu yaşam-döngüsünü (register → discover → health →
trust → activate → remove) yönetir, **trust governance** (Madde 24) uygular ve sunucu kaydını **kalıcılaştırır**
(restart'ta hub'a geri yüklenir). Çekirdek MCPHub **değiştirilmez** (yalnız additive `get_server`/`remove_server`
eklendi).

## Trust governance (Madde 24)
Seviyeler: `untrusted < trusted < verified`. **Yürütme-zamanı kapısı zaten çekirdektedir** (`map_and_bind`:
untrusted sunucunun riskli aracı → kullanıcı onayı ister). Bu domain **trust yaşam-döngüsünü** (admin promosyonu
+ denetim), **kalıcılığı** ve **görünürlüğü** ekler. `activate` raporu, onay-kapılı (untrusted) sunucuları
`trust_gated_servers` olarak listeler.

## Public API (`MCPManagementDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_server(actor, name, url, transport, trust_level, sandboxed)` | Sunucu kaydı (admin) |
| `discover(actor)` | İstemciyle sunucu/araç keşfi (istemci yoksa 0 — dürüst) |
| `health_check(actor)` | Sağlık güncelle (unknown/healthy/degraded/down) |
| `set_trust(actor, server_id, trust_level)` | Trust yaşam-döngüsü (admin + denetim) |
| `activate(actor)` | Sağlıklı sunucuların araçlarını Capability+executor bağla (hub'a delege) |
| `remove_server / describe / list_servers / lifecycle_history / stats / contract` | Yaşam-döngüsü + sorgu + sözleşme |

## Invariantlar
- untrusted sunucunun riskli araçları yürütmede **kullanıcı onayı** ister (çekirdek kapısı; Madde 24).
- Trust değişimi **admin** yetkisi ister ve **denetlenir** (append-only lifecycle).
- Sunucu kaydı **kalıcı** (restart'ta `restore()` ile hub'a döner; araçlar discover'da yeniden dolar).
- Çekirdek MCPHub **sarılır, değiştirilmez** (Madde 15/16).

## Yetki
Okuma/health: owner + Executive/Operations/Security/Engineering/Workflow. Yönetim (register/discover/trust/
activate/remove): **admin** = owner + Executive + Operations + Security.

## Production bileşenleri (placeholder YOK)
Model (çekirdek MCP yeniden-kullanım) · Repository (SQLite: server registry + append-only lifecycle) · Contract
v1.0.0 · Events (registered/discovered/health_checked/trust_changed/activated/removed) · Authorization (admin
ayrımı) · Validation · Error hiyerarşisi · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_mcp_mgmt_domain.py`) · Docs.

## Bağımlılıklar (DI)
`MCPManagementDomain(hub: MCPHub, repository, capabilities=CapabilityRegistry, orchestrator=ToolOrchestrator,
meta=MetaMCPManager, bus, config)` — `runtime.boot()` bağlar (`mio.mcp_management`; ham `mio.mcp_hub`/`mio.meta`
korunur), boot'ta `restore()` çağrılır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
