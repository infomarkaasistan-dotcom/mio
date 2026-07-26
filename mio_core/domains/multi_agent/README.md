# Multi-Agent Domain (Faz 5 · Domain 36) — Maturity: STABLE

> Constitution refs: **Madde 3 (Executive tek karar vericidir; alt birim tek başına karar vermez)**, Madde 24
> (yüksek-risk görev onay), Madde 6/7 (uzak agent adapter üzerinden), Madde 8 (dürüstlük), Madde 16.
> **Compliance: FULLY COMPLIANT (kapsam içi).**

**Anayasa gereği Executive tek karar vericidir; agent'lar deterministik atamayla İŞ YÜRÜTÜR, tek başına KARAR
VERMEZ** (vertikal beyin deseniyle aynı ilke). Çekirdek: agent registry (rol/yetenek/güven/kapasite) +
**deterministik görev atama** (yetenek eşleşmesi + güven + boş kapasite) + koordinasyon durum makinesi
(pending→assigned→working→completed/failed/**no_agent**/**no_connector**/**requires_approval**). Gerçek uzak agent
çağrısı enjekte edilen **executor adapter (DI)**'a delege. **Uygun agent yoksa `no_agent`; executor yoksa
`no_connector`** (Madde 8). Gerçek uzak yürütme **çekirdekte yok**.

## Public API (`MultiAgentDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_executor(agent_id, fn, name)` | GERÇEK uzak yürütme connector'ı bağla (DI) |
| `register_agent(actor, name, role, capabilities, trust, max_load, status)` | Agent kaydı |
| `submit_task(actor, title, required_capabilities, payload, priority, risk, user_approved)` | Görev → deterministik ata+yürüt; high+onaysız `requires_approval` |
| `approve_task(actor, task_id)` | Onay bekleyen yüksek-risk görevi onayla+yürüt (**owner/Executive**) |
| `get_task / list_tasks / list_agents / eligible_agents / executors / stats / contract` | Sorgu + sözleşme |

## Deterministik atama (Anayasa Madde 3 · LLM'siz)
`_eligible`: **ACTIVE** + `capabilities ⊇ required` + boş kapasitesi (`max_load - active_load > 0`) olan agent'lar.
Aralarından `assignment_score = (trust, spare, name)` en büyüğü seçilir. **Aynı koşul → aynı agent.** LLM bu atamayı
VERMEZ; yalnız operatör politikası (güven/kapasite) ve ölçülebilir eşleşme belirler.

## Güvenlik (Madde 24 · deterministik)
`classify_risk`: bildirilen `risk=high` **veya** başlık tehlikeli işaret içeriyorsa (`delete/deploy/publish/
transfer/pay/purchase/shutdown/release/sil/yayınla/gönder/öde/dağıt/devreye al`) → **high**. Yüksek-risk +
`user_approved=False` → **`requires_approval`** (yürütülmez). Onay yalnız **owner/Executive**.

## Invariantlar
- **Executive tek karar verici:** agent iş yürütür, karar VERMEZ (Madde 3).
- **Deterministik atama:** LLM karar verici değil.
- **Dürüstlük (Madde 8):** uygun agent yoksa `no_agent`; executor yoksa `no_connector`; uydurma sonuç yok.
- **Onay şart (Madde 24):** yüksek-risk görev onaysız EXECUTED olmaz.

## Yetki
Okuma: owner + Executive/Operations/Engineering/Planning/Reasoning/Perception. Yönetim/görev: owner + Executive/
Operations/Engineering/Planning. **Onay: owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (Agent/AgentTask + deterministik `assignment_score` + risk classifier) · Repository (SQLite; agent/
agent_task + `active_load`) · Contract v1.0.0 · Events (registered/task_submitted/assigned/completed/failed/
no_agent/no_connector/approval_required/approved) · Authorization (approver ayrımı) · Validation · Error
hiyerarşisi · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_multi_agent_domain.py`) · Docs.

## Bağımlılıklar (DI)
`MultiAgentDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.multi_agent`). Gerçek executor'lar
sonradan `register_executor` ile bağlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek uzak agent executor'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
