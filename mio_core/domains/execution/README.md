# Execution Domain (Faz 2 · Domain 9) — v1.0.0 · FROZEN

Onaylı karar/planı **gerçek araçlarla** (Tool Orchestrator) hayata geçirir. Anayasa: **Execution ASLA tek
başına karar VERMEZ** — her yürütme bir yetkilendirmeye (onaylı plan ya da karar referansı) bağlıdır. Bir
workflow, **yalnız APPROVED** bir planın sıralı adımlarını çalıştırır (fail-fast) ve her adımı denetime yazar.
İsteğe bağlı olarak her adım sonucu Learning'e beslenir → **Plan → Execute → Learn** döngüsü kapanır.

## Public API (`ExecutionDomain`)
| Operasyon | Açıklama |
|---|---|
| `run_capability(actor, capability, action, params, authorization, ...)` | Tek yetenek yürüt (yetkilendirme zorunlu) |
| `run_plan(actor, plan_id)` | APPROVED planı workflow olarak yürüt (fail-fast) |
| `history` / `explain(run_id)` | Yürütme denetim izi (workflow düzeyi) |
| `stats` / `contract` | Observability + versioned sözleşme |

## Invariantlar
- **Yetkilendirme zorunlu:** `run_capability` boş authorization ile → `UnauthorizedExecutionError`.
- **Yalnız onaylı plan:** `run_plan` plan `approved` değilse reddeder (Execution tek başına karar vermez).
- **Fail-fast + denetim:** ilk başarısız adımda durur; her adım (skip dahil) koşu kaydına yazılır.
- **Governance orchestrator'da:** izin/onay/verdict Tool Orchestrator'da uygulanır — bu domain onu sarar.

## Yetki
Okuma: owner + Executive/Operations/Workflow/Engineering. Başlatma (run_*): owner + Executive/Operations/Workflow.

## Production bileşenleri (placeholder YOK)
Model (ExecutionRun) · Repository (SQLite write-through) · Contract v1.0.0 · Events (capability_run/
plan_run_started/plan_run_finished/step_executed/blocked) · Authorization · Validation · Error hiyerarşisi ·
Observability (metrics+log+events) · Config · Unit+Integration+Smoke (`tests/test_execution_domain.py`) · Docs.

## Bağımlılıklar (DI)
`ExecutionDomain(orchestrator, repository, planning=PlanningDomain, learning=LearningDomain, bus, config)` —
`runtime.boot()` bağlar (`mio.execution`). planning/learning opsiyoneldir.

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
