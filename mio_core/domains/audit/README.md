# Audit & Compliance Domain (Constitution Faz 2 · Domain 18) — Maturity: STABLE

> Constitution refs: Madde 36 (Constitutional Compliance), Madde 27 (Observability), Governance Extensions
> §10 (Compliance Levels). **Compliance: FULLY COMPLIANT (kapsam içi).**

İki sorumluluk: (1) platform-geneli **değişmez (append-only) audit ledger** — kim, neyi, hangi kaynağa,
hangi sonuçla; (2) **Constitution Compliance** durumunu **sorgulanabilir veri** olarak tutar (yalnız markdown
değil) — Madde 36/§10 uyum seviyeleri. Security Domain'in RBAC-audit'ini **tamamlar** (ayrı kapsam:
security-event değil, platform kritik-işlem + uyum).

## Public API (`AuditComplianceDomain`)
| Operasyon | Açıklama |
|---|---|
| `log(actor, action, resource, outcome, severity, detail)` | Değişmez ledger'a kritik işlem yaz |
| `trail(actor, target_actor, action, outcome, limit)` | Audit sorgusu (auditor) |
| `assess(actor, scope, article, level, note, planned_phase)` | Uyum değerlendirmesi kaydet (admin) |
| `register_exception(actor, scope, article, reason, planned_phase)` | Bilinçli istisna (EXCEPTION APPROVED) |
| `compliance_report(actor)` | Güncel uyum; **genel seviye = 'en kötü' kayıt** (deterministik) |
| `stats` / `contract` | Observability + versioned sözleşme |

## Uyum seviyeleri (§10)
`fully_compliant > substantially_compliant > partially_compliant > exception_approved > non_compliant`.
Genel seviye deterministik olarak **en düşük** kayıtla belirlenir.

## Invariantlar
- **Audit ledger append-only** (değişmez).
- **Compliance yazımı admin** yetkisi ister ve **kendisi de denetlenir** (izlenebilirlik).
- **İstisna** gerekçe + planlanan faz zorunlu kılar (§10 EXCEPTION APPROVED).

## Yetki
Okuma/rapor: owner + Executive/Security/Operations/Compliance/Legal. Audit **yazımı** geniş (yetkili her
bileşen kritik işlemi kaydeder). Compliance değerlendirmesi/istisna: **admin** = owner + Executive + Security +
Compliance.

## Production bileşenleri (placeholder YOK)
Model (AuditRecord/ComplianceRecord) · Repository (SQLite: append-only ledger + compliance upsert) · Contract
v1.0.0 · Events (logged/compliance_assessed/exception_registered) · Authorization (admin ayrımı) · Validation ·
Error hiyerarşisi · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_audit_domain.py`) · Docs.

## Bağımlılıklar (DI)
`AuditComplianceDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.audit`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
