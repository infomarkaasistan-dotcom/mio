# Sales & CRM Domain (Faz 3 · Domain 26) — Maturity: STABLE

> Constitution refs: Madde 9 (operasyon yönetimi), Governance Extensions §9 (LLM danışman). **Compliance:
> FULLY COMPLIANT (kapsam içi).**

Advisory **Vertical Sales Brain**'in operasyonel karşılığı. Deterministik **CRM/pipeline**: contact (lead/
customer) + opportunity (stage: lead→qualified→proposal→negotiation→won/lost) + **ağırlıklı pipeline
metrikleri** (ağırlık = stage kazanma olasılığı) + **lead qualification** (soğuk-lead → değer-önce). Hesaplar
deterministik; qualification **öneri**, karar Executive'de.

## Public API (`SalesCRMDomain`)
| Operasyon | Açıklama |
|---|---|
| `add_contact(actor, name, kind, email, company)` | Contact (lead/customer) |
| `add_opportunity(actor, contact_id, title, value, stage)` | Fırsat (pipeline'a) |
| `advance_stage(actor, opp_id, stage)` | Aşama değiştir |
| `pipeline(actor)` | Stage dağılımı + open/weighted value + win_rate |
| `qualify(actor, context_tags)` | Deterministik lead qualification önerisi |
| `list_contacts / list_opportunities / stats / contract` | Sorgu + sözleşme |

## Deterministik metrikler
- **weighted_value** = Σ (value × stage_probability) [lead .1, qualified .3, proposal .5, negotiation .7].
- **win_rate** = won / (won + lost); kapalı fırsat yoksa `null` (dürüst).

## Invariantlar
- **Determinizm:** pipeline metrikleri aynı veri → aynı sonuç.
- **Öneri, karar değil:** qualification `decision_authority = Executive`.

## Yetki
Okuma/pipeline/qualify: owner + Executive/Sales/Marketing/Operations/Business/Planning/Reasoning. Yazma:
owner + Executive/Sales/Operations.

## Production bileşenleri (placeholder YOK)
Model (Contact/Opportunity) · Repository (SQLite) · Contract v1.0.0 · Events (contact_added/opportunity_added/
stage_changed/qualified) · Authorization · Validation · Error hiyerarşisi · Observability (metrics+events) ·
Config · Unit+Integration+Smoke (`tests/test_sales_domain.py`) · Docs.

## Bağımlılıklar (DI)
`SalesCRMDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.sales`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
