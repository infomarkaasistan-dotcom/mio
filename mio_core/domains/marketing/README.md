# Marketing & Growth Domain (Faz 3 · Domain 27) — Maturity: STABLE

> Constitution refs: Madde 9 (operasyon yönetimi), Madde 8 (dürüstlük — sıfıra bölme uydurma değil),
> Governance Extensions §9 (LLM danışman). **Compliance: FULLY COMPLIANT (kapsam içi).**

Advisory **Vertical Marketing Brain**'in operasyonel karşılığı. Deterministik **kampanya yönetimi**:
kampanya (kanal/bütçe/hedef) + **kümülatif metrik** (impressions/clicks/conversions/spend/revenue) +
**türetilen KPI** (CTR/CVR/CPC/CPA/**ROAS**/budget_used) + **kanal kırılımı**. Hesaplar deterministik;
**sıfıra bölme dürüstçe `None`** (uydurma yok).

## Public API (`MarketingDomain`)
| Operasyon | Açıklama |
|---|---|
| `create_campaign(actor, name, channel, budget, target)` | Kampanya oluştur |
| `record_metrics(actor, id, impressions, clicks, conversions, spend, revenue)` | Metrik **kümülatif** ekle |
| `set_status(actor, id, status)` | draft/active/paused/ended |
| `performance(actor, id)` | Metrikler + KPI'lar (CTR/CVR/CPC/CPA/ROAS/budget) |
| `channel_breakdown(actor)` | Kanal bazında spend/revenue/ROAS |
| `list_campaigns / stats / contract` | Sorgu + sözleşme |

## KPI'lar (deterministik)
`ctr = clicks/impressions` · `cvr = conversions/clicks` · `cpc = spend/clicks` · `cpa = spend/conversions` ·
`roas = revenue/spend` · `budget_used = spend/budget`. Payda 0 → `None` (dürüst). Tutarlılık: `clicks ≤
impressions`, `conversions ≤ clicks` doğrulanır.

## Invariantlar
- **Determinizm:** aynı metrik → aynı KPI.
- **Dürüstlük:** sıfıra bölme None; imkânsız oran (clicks>impressions) reddedilir.
- **Kümülatif:** metrikler biriktirilir.

## Yetki
Okuma/performance: owner + Executive/Marketing/Sales/Operations/Business/Planning/Reasoning. Yazma:
owner + Executive/Marketing/Operations.

## Production bileşenleri (placeholder YOK)
Model (Campaign) · Repository (SQLite) · Contract v1.0.0 · Events (campaign_created/metrics_recorded/
status_changed) · Authorization · Validation (tutarlılık) · Error hiyerarşisi · Observability (metrics+events) ·
Config · Unit+Integration+Smoke (`tests/test_marketing_domain.py`) · Docs.

## Bağımlılıklar (DI)
`MarketingDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.marketing`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
