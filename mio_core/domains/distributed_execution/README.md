# Distributed Execution Domain (Faz 5 · Domain 40) — Maturity: STABLE

> Constitution refs: **Madde 3/4 (Execution tek başına karar vermez)**, Madde 24 (yüksek-risk dağıtık iş onay),
> Madde 6/7 (uzak düğüm adapter üzerinden), Madde 8 (dürüstlük), Madde 16. **Compliance: FULLY COMPLIANT
> (kapsam içi).**

**Anayasa gereği Execution tek başına karar vermez; iş dağıtımı DETERMİNİSTİK politikadır; yüksek-risk/geri-alınamaz
dağıtık iş ONAY ister (Madde 24).** Çekirdek: worker node registry (kapasite/yetenek/sağlık) + **deterministik iş
dağıtım/zamanlama** (yetenek eşleşmesi + kapasite + öncelik) + dağıtık iş durum makinesi (queued→scheduled→running→
completed/failed/**no_node**/**no_connector**/**requires_approval**) + **idempotency** (deterministik iş kimliğiyle
effectively-once). Gerçek uzak çalıştırma enjekte edilen **node executor adapter (DI)**'a delege. **Uygun düğüm
yoksa `no_node`; executor yoksa `no_connector`** (Madde 8). Gerçek uzak yürütme **çekirdekte yok**. Multi-Agent'ın
altyapı-düzeyi kardeşi (agent yerine worker node).

## Public API (`DistributedExecutionDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_executor(node_id, fn, name)` | GERÇEK uzak çalıştırma connector'ı bağla (DI) |
| `register_node(actor, name, capabilities, capacity, status, region)` | Düğüm kaydı |
| `set_node_status(actor, node_id, status)` | Sağlık değişimi (healthy/draining/down) |
| `submit(actor, task, required_capabilities, payload, priority, risk, idempotency_key, user_approved)` | İş gönder — deterministik dağıt+yürüt; high+onaysız `requires_approval` |
| `approve_job(actor, job_id)` | Onay bekleyen yüksek-risk işi onayla+dağıt (**owner/Executive**) |
| `get_job / list_jobs / list_nodes / eligible_nodes / executors / stats / contract` | Sorgu + sözleşme |

## Deterministik zamanlama (Madde 3 · LLM'siz)
`_eligible`: **HEALTHY** + `capabilities ⊇ required` + boş kapasitesi (`capacity - active_load > 0`) olan düğümler.
`schedule_score = (spare, name)` en büyüğü (en boş düğüm) seçilir. **Aynı koşul → aynı düğüm.** LLM bu dağıtımı
VERMEZ.

## Idempotency (effectively-once)
`submit(idempotency_key=...)`: aynı anahtarlı **canlı/başarılı** (queued/scheduled/running/completed/no_connector/
requires_approval) iş varsa **yeni iş yaratılmaz**, mevcut döner (`job_deduped`). Yalnız `failed` yeniden denenir.

## Güvenlik (Madde 24 · deterministik)
`classify_risk`: bildirilen `risk=high` **veya** görev tehlikeli işaret içeriyorsa (`delete/drop/destroy/migrate/
truncate/wipe/purge/sil/taşı/yok et/biçimlendir`) → **high**. Yüksek-risk + `user_approved=False` →
**`requires_approval`** (dağıtılmaz). Onay yalnız **owner/Executive**.

## Invariantlar
- **Deterministik dağıtım:** LLM karar verici değil; Execution tek başına karar vermez.
- **Sağlık/kapasite:** yalnız HEALTHY + yetenekli + boş kapasiteli düğüme dağıtılır.
- **Effectively-once:** idempotency_key ile canlı/başarılı iş tekrarlanmaz.
- **Dürüstlük (Madde 8):** düğüm yoksa `no_node`; executor yoksa `no_connector`.
- **Onay şart (Madde 24):** yüksek-risk iş onaysız çalışmaz.

## Yetki
Okuma: owner + Executive/Operations/Engineering/Planning/Scheduler/Execution. Yönetim/iş: owner + Executive/
Operations/Engineering/Scheduler. **Onay: owner + Executive.**

## Production bileşenleri (placeholder YOK)
Model (Node/DistributedJob + deterministik `schedule_score` + risk classifier + idempotency semantiği) ·
Repository (SQLite; node/dist_job + idempotency index + `active_load`) · Contract v1.0.0 · Events (node_registered/
status_changed/job_submitted/deduped/scheduled/completed/failed/no_node/no_connector/approval_required/approved) ·
Authorization (approver ayrımı) · Validation · Error hiyerarşisi · Observability (metrics+events) · Config ·
Unit+Integration+Smoke (`tests/test_distributed_execution_domain.py`) · Docs.

## Bağımlılıklar (DI)
`DistributedExecutionDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.distributed_execution`).
Gerçek executor'lar sonradan `register_executor` ile bağlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek uzak node executor'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
