# Planning Domain (Faz 1 · Domain 5) — v1.0.0 · FROZEN

Bir amaca hizmet eden; **bağımlılık-sıralı, yetenek-farkında, DETERMİNİSTİK** plan üretimi. Planning
**yürütmez** ve **karar vermez** — plan üretir, sıralar, fizibilitesini denetler. Onay Executive/E4'e,
yürütme Execution'a aittir ("Execution asla tek başına karar vermez").

## Public API (`PlanningDomain`)
| Operasyon | Açıklama |
|---|---|
| `draft_plan(actor, objective, goal_id)` | Yeni plan taslağı (bir amaca bağlı) |
| `add_step(actor, plan_id, desc, requires, capability, expected)` | Bağımlılıklı adım ekle |
| `sequence(actor, plan_id)` | **Kararlı topolojik sıralama**; döngü → InfeasiblePlanError |
| `assess(actor, plan_id)` | Fizibilite: dangling dep, döngü, bilinmeyen yetenek, kapsam |
| `mark_approved(actor, plan_id)` | Onaylı işaretle (Executive/E4; fizibil + sıralı olmalı) |
| `abandon` / `plan_view` / `list_plans` / `stats` / `contract` | Yaşam-döngüsü + observability + sözleşme |

## Invariantlar
- **Determinizm:** aynı plan → aynı sıralama (Kahn + kararlı ekleme-sırası tie-break).
- **Fizibilite:** döngü ve çözülemeyen bağımlılık reddedilir.
- **Yetki ayrımı:** planning onaylamaz/yürütmez; `mark_approved` yalnız Executive/E4, plan fizibil+sıralı ise.

## Yetki
Okuma: owner + Executive/Planning/Reasoning/Knowledge/Learning. Yazma (draft/step/sequence/abandon):
owner + Executive/Planning. Onay: owner + Executive.

## Production bileşenleri (placeholder YOK)
Model (Plan/PlanStep) · Repository (SQLite write-through) · Contract v1.0.0 · Events (drafted/step_added/
sequenced/approved/abandoned) · Authorization · Validation · Error hiyerarşisi · Observability
(metrics+log+events) · Config · Unit+Integration+Smoke (`tests/test_planning_domain.py`) · Docs.

## Bağımlılıklar (DI)
`PlanningDomain(repository, capabilities=CapabilityRegistry, reasoning=ReasoningDomain, bus, config)` —
`runtime.boot()` bağlar (`mio.planning`). capabilities/reasoning opsiyoneldir (fizibiliteyi bozmaz).

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
