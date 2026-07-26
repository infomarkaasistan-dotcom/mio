# Data Analytics Domain (Faz 3 · Domain 23) — Maturity: STABLE

> Constitution refs: Madde 8 (dürüstlük/no-mock), Madde 16 (küçük çekirdek — ağır kütüphane yok),
> Governance Extensions §9 (LLM danışman). **Compliance: FULLY COMPLIANT (kapsam içi).**

Deterministik **tablo analitiği** (stdlib `statistics`, pandas YOK): dataset registry + **describe** (sütun
tipi/istatistik) + **aggregate/KPI** (sum/mean/min/max/median/count/distinct) + **trend** (yön/değişim%) +
**anomali** (mean ± k·std). **Uydurma yok** — yalnız verilen veriden hesaplanır. LLM ancak narrative/yorum için
danışman olabilir; hesaplar çekirdektedir.

## Public API (`DataAnalyticsDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_dataset(actor, name, rows)` | Dataset kaydet (rows = dict listesi) |
| `describe(actor, dataset_id)` | Her sütun: tip + count/distinct/min/max/mean/sum |
| `aggregate(actor, dataset_id, column, op)` | Deterministik aggregate |
| `kpi(actor, dataset_id, name, column, op)` | Adlandırılmış KPI = aggregate |
| `trend(actor, series)` | Yön (up/down/flat) + değişim% |
| `anomalies(actor, series, k)` | mean ± k·std dışı değerler |
| `list_datasets / stats / contract` | Sorgu + observability + sözleşme |

## Invariantlar
- **Determinizm:** aynı veri → aynı sonuç.
- **Uydurma yok:** yalnız verilen veriden; sayısal olmayan sütunda değer yerine dürüst not.
- **Anomali:** deterministik eşik (mean ± k·std).

## Yetki
Okuma/analiz: owner + Executive/Operations/Finance/Marketing/Sales/Research/Planning/Reasoning/Business.
Yazma (register): owner + Executive/Operations/Finance/Research.

## Production bileşenleri (placeholder YOK)
Model (Dataset) · Analyzer (statistics, deterministik) · Repository (SQLite) · Contract v1.0.0 · Events
(dataset_registered/aggregated/kpi_computed/anomaly_found) · Authorization · Validation · Error hiyerarşisi ·
Observability (metrics+events) · Config · Unit+Integration+Smoke (`tests/test_data_analytics_domain.py`) · Docs.

## Bağımlılıklar (DI)
`DataAnalyticsDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.data_analytics`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
