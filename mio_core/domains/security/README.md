# Security Domain (Faz 4 · Domain 15) — v1.0.0 · FROZEN

Merkezî **kimlik + yetki (RBAC)** + **append-only güvenlik denetimi** + **secret redaksiyonu** + **kilitleme**.
Her domain'in kendi yetki-config'i vardır; bu domain sistem-geneli RBAC ve güvenlik olay denetimini
merkezîleştirir. Anayasa'nın *"secret asla loglanmaz"* ilkesini `redact()` ile birinci-sınıf yapar.

## RBAC (deterministik)
Etkin izinler = **rol izinleri ∪ doğrudan grant'ler**. Roller: `owner` (süper kullanıcı) · `executive` ·
`operations` · `security` · `brain`. İzinler: `read/write/execute/admin/financial/security_admin`. `check`
kararı deterministiktir; **ardışık başarısız kontrol** `lockout_threshold`'u aşınca principal **kilitlenir**.

## Public API (`SecurityDomain`)
| Operasyon | Açıklama |
|---|---|
| `check(principal, permission, resource)` | Deterministik RBAC kararı + denetim (kilit mantığı dahil) |
| `authorize(principal, permission)` | `check(...)["allowed"]` kısayolu |
| `register_principal / grant / revoke / assign_role` | Kimlik yönetimi (admin) |
| `lock / unlock` | Kilitleme yönetimi (admin) |
| `record_event(actor, kind, detail, severity)` | Güvenlik olayı yaz (detail **redakte edilir**) |
| `audit_trail(actor, limit, principal)` | Append-only denetim izi (admin) |
| `redact(text)` | Secret desenlerini maskele (saf/deterministik) |
| `stats / contract` | Observability + versioned sözleşme |

## Invariantlar
- **Deterministik yetki:** aynı principal + izin → aynı karar.
- **Append-only denetim** ve **her detail redakte** edilerek yazılır (secret sızıntısı yok).
- **Kilitleme:** ardışık başarısızlık eşiği aşınca otomatik kilit (WARNING/CRITICAL audit).
- **Innate kimlikler** doğuşta gelir (owner süper kullanıcı + çekirdek roller + beyinler).

## Yetki
Yönetim + audit trail: **admin** = owner + Executive + Security. `check`/`redact` sistem-içi kullanım.

## Production bileşenleri (placeholder YOK)
Model (Principal/SecurityAudit + RBAC + redact) · Repository (SQLite: principals + append-only audit) ·
Contract v1.0.0 · Events (check/denied/principal_changed/locked/unlocked/audit) · Authorization (admin ayrımı) ·
Validation · Error hiyerarşisi · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_security_domain.py`) · Docs.

## Bağımlılıklar (DI)
`SecurityDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.security`), doğuştan kimliklerle gelir.

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
