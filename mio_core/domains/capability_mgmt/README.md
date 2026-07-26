# Capability Management Domain (Constitution Faz 2 · Domain 16) — v1.0.0 · FROZEN

> Constitution refs: Madde 15 (Evolutionary — sar, yeniden yazma), Madde 16 (küçük çekirdek), Madde 26
> (Capability Evolution), Madde 29 (Versioned Contracts), Governance Extensions §7 (Maturity Levels).
> **Compliance: FULLY COMPLIANT.**

Çekirdek `CapabilityRegistry`'yi (Born Capable in-memory aggregate) **saran** governance kabuğu. Yetenek
olgunluk yaşam-döngüsünü yönetir, deterministik yetenek seçimi yapar ve Capability Evolution'ı denetler.
Çekirdek registry **değiştirilmez**; bu domain onu sarar (Madde 15/16).

## Maturity yaşam-döngüsü (§7, deterministik)
`experimental → preview → stable → production` (ileri) · her USABLE seviyeden `→ deprecated → retired`.
**retired terminaldir.** Geçersiz geçiş (ör. `retired → stable`) reddedilir. Executive seçimde yalnız
**USABLE** (experimental/preview/stable/production) + **connected** yetenekleri değerlendirir.

## Public API (`CapabilityManagementDomain`)
| Operasyon | Açıklama |
|---|---|
| `register(actor, name, …, maturity, contract_version, …)` | Yönetilen yetenek kaydı (admin) |
| `set_maturity / deprecate / retire` | §7 yaşam-döngüsü geçişleri (admin) |
| `set_connected(actor, name, connected)` | Keşif sonucu (bağlı/değil) |
| `select_best(actor, category, brain, only_connected)` | **Deterministik** en iyi yetenek (maturity sırası + priority) |
| `usable(actor, name)` | Şu an yürütmeye seçilebilir mi? (USABLE + connected) |
| `describe / list_capabilities / lifecycle_history / stats / contract` | Sorgu + evolution denetimi + sözleşme |

## Kalıcılık (Madde 26/29)
Maturity/contract override'ları write-through SQLite'a yazılır ve **boot'ta `restore()`** ile in-memory
registry'ye geri uygulanır (Born Capable + kalıcı evolution). Ayrıca **append-only lifecycle log** (registered/
maturity_changed/connected) evolution geçmişini tutar.

## Invariantlar
- Maturity geçişleri §7 kurallarına uyar; retired terminaldir.
- Yetenek seçimi deterministiktir (maturity sırası + priority); yalnız USABLE+connected seçilir.
- Çekirdek registry sarılır, değiştirilmez.

## Yetki
Okuma: owner + Executive/Operations/Planning/Reasoning/Engineering/Workflow. Yönetim (register/maturity/
connect): **admin** = owner + Executive + Operations.

## Production bileşenleri (placeholder YOK)
Model (çekirdek Capability yeniden-kullanım + §7 geçiş tablosu) · Repository (SQLite: state override + append-only
lifecycle) · Contract v1.0.0 · Events (registered/maturity_changed/connected/selected) · Authorization ·
Validation · Error hiyerarşisi · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_capability_mgmt_domain.py`) · Docs.

## Bağımlılıklar (DI)
`CapabilityManagementDomain(registry: CapabilityRegistry, repository, bus, config)` — `runtime.boot()` bağlar
(`mio.capability_management`; ham `mio.capabilities` registry korunur), boot'ta `restore()` çağrılır.

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
