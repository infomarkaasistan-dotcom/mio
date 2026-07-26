# Customer Success Domain (Faz 3 · Domain 28) — Maturity: STABLE

> Constitution refs: Madde 9 (operasyon yönetimi), Madde 8 (dürüstlük), Governance Extensions §9 (LLM
> danışman). **Compliance: FULLY COMPLIANT (kapsam içi).** *(Faz 3 Intelligence Domains'in son domaini.)*

Deterministik **müşteri başarısı**: account + support ticket (öncelik/durum) + CSAT (1-5) + **deterministik
health score** + **churn-risk** bayrağı. Hesaplar yalnız kayıtlı veriden (uydurma yok).

## Health score (deterministik)
`health = 100 − Σ(açık ticket ağırlığı) + (avg_csat − 3)×10`, `[0,100]` kırpılır. Ticket ağırlığı: low 3,
medium 7, high 15. `churn_risk = health < churn_risk_below` (varsayılan 50). CSAT yoksa nötr (3) kabul.

## Public API (`CustomerSuccessDomain`)
| Operasyon | Açıklama |
|---|---|
| `add_account(actor, name, tier)` | Müşteri hesabı |
| `open_ticket(actor, account_id, subject, priority)` | Destek talebi |
| `update_ticket(actor, ticket_id, status)` | open/in_progress/resolved |
| `record_feedback(actor, account_id, score)` | CSAT (1-5) |
| `health(actor, account_id)` | **Deterministik health score + churn_risk** |
| `list_accounts / list_tickets / stats / contract` | Sorgu + sözleşme |

## Invariantlar
- **Determinizm:** aynı ticket/feedback → aynı health.
- **Churn-risk:** health < eşik (deterministik).
- **CSAT 1-5** doğrulanır.

## Yetki
Okuma/health: owner + Executive/CustomerSuccess/Sales/Operations/Business/Planning/Reasoning. Yazma:
owner + Executive/CustomerSuccess/Operations.

## Production bileşenleri (placeholder YOK)
Model (Account/Ticket/Feedback) · Repository (SQLite) · Contract v1.0.0 · Events (account_added/ticket_opened/
ticket_resolved/feedback_recorded/churn_risk) · Authorization · Validation · Error hiyerarşisi · Observability
(metrics+events) · Config · Unit+Integration+Smoke (`tests/test_customer_success_domain.py`) · Docs.

## Bağımlılıklar (DI)
`CustomerSuccessDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.customer_success`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
