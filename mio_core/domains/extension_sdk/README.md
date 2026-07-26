# Extension SDK Domain (Faz 5 · Domain 43 — SON ana domain) — Maturity: STABLE

> Constitution refs: **Madde 24 (denetlenmemiş/aşırı-izinli uzantı onaysız etkinleştirilemez)**, Madde 6/7 (host
> sandbox adapter üzerinden), Madde 8 (dürüstlük), Madde 27 (görünür hata), Madde 16. **Compliance: FULLY
> COMPLIANT (kapsam içi).** Bu domain **Faz 5'i ve tüm ana domainleri tamamlar**.

**Anayasa gereği denetlenmemiş/aşırı-izinli üçüncü-taraf uzantı platforma SOKULAMAZ; etkinleştirme ONAY ister
(Madde 24).** Çekirdek: uzantı (extension) manifest registry (ad/sürüm/tür/istenen-izinler/imza) + **deterministik
manifest & izin-kapsamı (scope) doğrulama** (yayıncı/imza allowlist + istenen izinlerin grantable-allowlist uyumu) +
uzantı yaşam-döngüsü (registered→validated→enabled→disabled/rejected). **Etkinleştirme yalnız owner/Executive**
(Madde 24); uyumsuz/aşırı-izinli **otomatik reddedilir**. **En-az-yetki:** yalnız istenen + izinli izinler verilir.
Uzantı çalıştırma enjekte edilen **host sandbox adapter (DI)**'a delege. **Host yoksa `no_connector`** (Madde 8).
Gerçek yürütme **çekirdekte yok**.

## Public API (`ExtensionSDKDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_host(kind, fn, name)` | GERÇEK host sandbox çalıştırma connector'ı bağla (DI) |
| `register_extension(actor, name, kind, version, entry, publisher, signature, requested_permissions)` | Manifest kaydı (REGISTERED; deterministik ön-değerlendirme) |
| `validate(actor, ext_id)` | Deterministik manifest+izin doğrula; uyumsuzsa OTOMATİK reddet |
| `enable(actor, ext_id)` | **Madde 24** etkinleştir (owner/Executive); en-az-yetki verir |
| `disable(actor, ext_id)` | Devre dışı bırak (izinler geri alınır) |
| `invoke(actor, ext_id, payload)` | Yalnız ENABLED → host sandbox'a delege; yoksa `no_connector` |
| `get_extension / list_extensions / hosts / permissions_catalog / stats / contract` | Sorgu + sözleşme |

## Deterministik doğrulama & en-az-yetki (Madde 24 · LLM'siz)
`ExtensionConfig.evaluate`: `publisher ∉ trusted_publishers` → `untrusted_publisher`; imza yoksa → `unsigned`;
geçersiz tür → `invalid_kind`; **istenen her izin `allowed_permissions` (grantable-allowlist) içinde değilse** →
`permission_not_allowed:<perm>`. Boş gerekçe → **geçerli**. `enable` onay anında yeniden doğrular (defense-in-depth)
ve **yalnız istenen + izinli** izinleri verir (`granted_permissions`).

## Yaşam-döngüsü durum makinesi
`registered → {validated, rejected}` · `validated → {enabled, disabled, rejected}` · `enabled → {disabled}` ·
`disabled → {enabled, rejected}` · `rejected` **terminal**. Çağrı yalnız `enabled`.

## Invariantlar
- **Denetim şart (Madde 24):** güvenilmez/imzasız/aşırı-izinli uzantı doğrulanamaz/etkinleştirilemez (otomatik red).
- **Onay sahibi:** yalnız owner/Executive etkinleştirir.
- **En-az-yetki:** yalnız istenen + grantable-allowlist'teki izinler verilir; disable → izin geri alınır.
- **Deterministik doğrulama:** LLM karar verici değil.
- **Dürüstlük (Madde 8):** host sandbox yoksa `no_connector`; **görünür hata (Madde 27):** invoke `failed`.

## Yetki
Okuma: owner + Executive/Operations/Engineering/Reasoning/Planning. Kayıt/doğrula/çağır/disable: owner + Executive/
Operations/Engineering. **Etkinleştir (enable): owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (Extension + deterministik `evaluate` + lifecycle TRANSITIONS + izin modeli) · Repository (SQLite) ·
Contract v1.0.0 · Events (registered/validated/rejected/enabled/disabled/invoked/invoke_failed/no_connector) ·
Authorization (approver ayrımı) · Validation · Error hiyerarşisi (+ TransitionError) · Observability
(metrics+events) · Config (publisher/izin allowlist) · Unit+Integration+Smoke
(`tests/test_extension_sdk_domain.py`) · Docs.

## Bağımlılıklar (DI)
`ExtensionSDKDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.extension_sdk`). Gerçek host
sandbox'lar `register_host` ile; yayıncı/izin allowlist'i `ExtensionConfig` ile ayarlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek host sandbox adapter'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
