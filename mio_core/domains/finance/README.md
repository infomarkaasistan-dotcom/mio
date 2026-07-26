# Finance Operations Domain (Faz 3 · Domain 25) — Maturity: STABLE

> Constitution refs: Madde 4 (Financial Rule — yükümlülük onaysız oluşmaz), Madde 8 (dürüstlük),
> Governance Extensions §9 (LLM danışman). **Compliance: FULLY COMPLIANT (kapsam içi).**

Advisory **Vertical Finance Brain**'in operasyonel karşılığı. Deterministik **gelir/gider defteri** + **nakit
akışı/runway** + **Financial Rule**: finansal yükümlülük (commitment) **onaysız EXECUTED olamaz** — talep daima
`pending_approval` başlar; yalnız **owner/Executive** onaylayabilir. Hesaplar deterministik (yalnız defterden;
uydurma yok). *(Policy Domain'in `financial-commitment-approval` PDP kuralı + Finance Brain guardrail'i ile
katmanlı; bu domain para tarafını operasyonel yürütür.)*

## Public API (`FinanceDomain`)
| Operasyon | Açıklama |
|---|---|
| `record_transaction(actor, kind, amount, category, currency, description)` | Gelir/gider defter girişi |
| `record_commitment(actor, description, amount)` | Yükümlülük TALEBİ → `pending_approval` (Financial Rule) |
| `approve_commitment / reject_commitment(actor, id)` | **Yalnız owner/Executive**; onay → gidere dönüşür |
| `cash_flow(actor)` | income / expense / net / balance |
| `category_breakdown(actor)` | Kategori kırılımı |
| `runway(actor, months)` | Bakiye / aylık burn → runway (deterministik) |
| `list_transactions / list_commitments / stats / contract` | Sorgu + sözleşme |

## Invariantlar
- **Financial Rule (Madde 4):** yükümlülük onaysız EXECUTED olamaz; onay owner/Executive'de.
- **Determinizm:** nakit akışı/runway yalnız defterden hesaplanır.
- **Dürüstlük:** burn=0 → runway "hesaplanamaz" (uydurma sonsuz vermez).

## Yetki
Okuma/analiz: owner + Executive/Finance/Operations/Business/Planning/Reasoning. Yazma (transaction/commitment):
owner + Executive/Finance/Operations. **Onay: owner + Executive** (Financial Rule).

## Production bileşenleri (placeholder YOK)
Model (Transaction/Commitment) · Repository (SQLite) · Contract v1.0.0 · Events (transaction_recorded/
commitment_requested/approved/rejected) · Authorization (approver ayrımı) · Validation · Error hiyerarşisi
(FinancialRuleError) · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_finance_domain.py`) · Docs.

## Bağımlılıklar (DI)
`FinanceDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.finance`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
