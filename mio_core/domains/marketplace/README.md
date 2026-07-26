# Marketplace / Ecosystem Domain (Faz 5 · Domain 37) — Maturity: STABLE

> Constitution refs: **Madde 24 (denetlenmemiş üçüncü-taraf yetenek onaysız platforma sokulamaz)**, Madde 6/7
> (dış kaynak adapter üzerinden), Madde 8 (dürüstlük), Madde 27 (görünür hata), Madde 16.
> **Compliance: FULLY COMPLIANT (kapsam içi).** `mio.marketplace_domain` (mevcut CapabilityMarketplace ile
> çakışmayı önlemek için `_domain` sonekiyle).

**Anayasa gereği denetlenmemiş üçüncü-taraf yetenek platforma SOKULAMAZ.** Çekirdek: yayın (listing) registry
(yetenek/eklenti/model/veri/MCP) + yayıncı/sürüm/imza + **deterministik uyumluluk & allowlist politikası** +
inceleme/kurulum durum makinesi (submitted→approved/rejected→installed/removed). **Onay yalnız owner/Executive**
(Madde 24); uyumlu/güvenilir değilse **otomatik reddedilir**. Gerçek indirme/kurulum enjekte edilen **kaynak
adapter (DI)**'a delege. **Installer yoksa `no_connector`** (Madde 8). Kurulum hatası **görünür**
(`install_failed` — Madde 27). Gerçek kurulum/çalıştırma **çekirdekte yok**.

## Public API (`MarketplaceDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_installer(kind, fn, name)` | GERÇEK indirme/kurulum connector'ı bağla (DI) |
| `submit_listing(actor, name, kind, publisher, version, source_uri, signature)` | Yayın gönder (SUBMITTED; deterministik ön-değerlendirme) |
| `check_compatibility(actor, listing_id)` | Deterministik uyumluluk raporu (salt-okunur) |
| `approve(actor, listing_id)` | **Madde 24** onay (owner/Executive); uyumsuzsa OTOMATİK reddeder |
| `reject(actor, listing_id, reason)` | Elle reddet (approver) |
| `install(actor, listing_id)` | Yalnız APPROVED → kaynak adapter'a delege; yoksa `no_connector` |
| `remove(actor, listing_id)` | Kaldır (INSTALLED/APPROVED → REMOVED) |
| `get_listing / list_listings / installers / stats / contract` | Sorgu + sözleşme |

## Deterministik uyumluluk & allowlist (Madde 24 · LLM'siz)
`MarketplaceConfig.evaluate`: `publisher ∈ trusted_publishers` **veya** kaynak host ∈ `trusted_sources`
(allowlist) değilse → `untrusted_source`; `require_signature` açık ve imza yoksa → `unsigned`; geçersiz tür →
`invalid_kind`. Gerekçe listesi boşsa **uyumlu**. `approve` uyumsuz listing'i **onaylayamaz** → otomatik `rejected`.

## Yaşam-döngüsü durum makinesi
`submitted → {approved, rejected}` · `approved → {installed, removed, rejected}` · `installed → {removed}` ·
`rejected`/`removed` **terminal**. Geçersiz geçiş → `TransitionError`. Kurulum yalnız `approved`.

## Invariantlar
- **Denetim şart (Madde 24):** güvenilmez/imzasız üçüncü-taraf yetenek onaylanamaz (otomatik red).
- **Onay sahibi:** yalnız owner/Executive onaylar/reddeder.
- **Deterministik uyumluluk:** LLM karar verici değil.
- **Dürüstlük (Madde 8):** installer yoksa `no_connector`; **görünür hata (Madde 27):** `install_failed`.

## Yetki
Okuma: owner + Executive/Operations/Engineering/Reasoning/Planning. Gönder/kur/kaldır: owner + Executive/
Operations/Engineering. **Onay/Red: owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (Listing + deterministik `evaluate` + lifecycle TRANSITIONS) · Repository (SQLite) · Contract v1.0.0 ·
Events (submitted/approved/rejected/installed/install_failed/no_connector/removed) · Authorization (approver
ayrımı) · Validation · Error hiyerarşisi (+ TransitionError) · Observability (metrics+events) · Config (allowlist)
· Unit+Integration+Smoke (`tests/test_marketplace_domain.py`) · Docs.

## Bağımlılıklar (DI)
`MarketplaceDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.marketplace_domain`). Gerçek
installer'lar sonradan `register_installer` ile bağlanır. Güven allowlist'i `MarketplaceConfig` ile ayarlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek kaynak/kurulum adapter'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
