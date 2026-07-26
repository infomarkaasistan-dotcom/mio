# Business & Operations Domain (Faz 3 · Domain 24) — Maturity: STABLE

> Constitution refs: Madde 9 (operasyon yönetimi), Madde 16 (küçük çekirdek), Governance Extensions §9
> (LLM danışman). **Compliance: FULLY COMPLIANT (kapsam içi).**

Deterministik **iş/operasyon yönetimi**: **süreç registry** (adım/rol/süre/otomatikleştirilebilirlik) +
**darboğaz/optimizasyon analizi** + **iş kuralı motoru** (koşul→aksiyon). Tümü deterministik; öneriler
**karar DEĞİL** — `decision_authority = Executive`.

## Public API (`BusinessOperationsDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_process(actor, name, steps)` | İş süreci kaydet (steps: name/role/duration_hours/automatable) |
| `analyze_process(actor, process_id)` | Toplam süre + **darboğaz** + otomasyon oranı + roller |
| `optimize_process(actor, process_id)` | Deterministik optimizasyon önerileri (otomasyon + darboğaz) |
| `register_rule(actor, name, when, then, priority)` | İş kuralı (koşul-tag → aksiyon) |
| `evaluate(actor, context_tags)` | Uyan kuralları priority-sıralı değerlendir → **öneri** aksiyonlar |
| `list_processes / list_rules / stats / contract` | Sorgu + observability + sözleşme |

## Invariantlar
- **Determinizm:** analiz ve kural değerlendirmesi aynı girdi → aynı sonuç.
- **Darboğaz:** tek adımın toplam süredeki oranı `bottleneck_ratio` (varsayılan 0.4) üstü.
- **Öneri, karar değil:** kural motoru aksiyon önerir; kararı Executive verir.

## Yetki
Okuma/analiz/evaluate: owner + Executive/Operations/Business/Workflow/Planning/Finance/Reasoning. Yazma
(process/rule): owner + Executive/Operations/Business/Workflow.

## Production bileşenleri (placeholder YOK)
Model (Process/ProcessStep/BusinessRule) · Repository (SQLite) · Contract v1.0.0 · Events (process_registered/
process_analyzed/rule_defined/rules_evaluated) · Authorization · Validation · Error hiyerarşisi · Observability
(metrics+events) · Config · Unit+Integration+Smoke (`tests/test_business_operations_domain.py`) · Docs.

## Bağımlılıklar (DI)
`BusinessOperationsDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.business_operations`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
