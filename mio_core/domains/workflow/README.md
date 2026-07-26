# Workflow Domain — Maturity: STABLE

> Constitution refs: **Katman ayrımı (domain ConnectorManager çağırmaz; görev CapabilityIntent taşır)**, Madde 3
> (Executive yürütür), Madde 24 (human-approval görevi onaysız çalışmaz), Madde 8/16. **Compliance: FULLY.**
> Kaynak: 2. nesil yol haritası **K1 (kritik eksik)** — `docs/architecture/SECOND_GENERATION_ROADMAP.md`.

Görev grafı (**DAG**) + yürütme planı + **checkpoint/resume** + **human-approval** + **rollback**. İş mantığı
(bağımlılık çözümü, döngü tespiti, topolojik sıra, checkpoint durumu) burada. **Domain ConnectorManager çağırmaz**;
her görev bir CapabilityIntent taşır — yürütmeye EXECUTIVE karar verir (`appservice.workflow_run` köprüsü).

## Public API (`WorkflowDomain`)
| Operasyon | Açıklama |
|---|---|
| `create_workflow(actor, name, tasks)` | DAG oluştur — döngü/eksik-bağımlılık **reddedilir** (DAGError) |
| `start / ready_tasks` | Yürütmeye başla / çalıştırılabilir görevler (bağımlılık tamam, onay engeli yok) |
| `complete_task / fail_task` | Checkpoint: görev tamam/başarısız → sonraki görevler otomatik ready |
| `approve_task(actor, wf, task)` | Human-approval görevini onayla → ready (**owner/Executive**, Madde 24) |
| `rollback(actor, wf, task)` | Görev + TÜM ardıllarını (deterministik descendant) pending yap |
| `plan(actor, wf)` | Topolojik yürütme planı (görev sırası + CapabilityIntent'ler) |
| `get_workflow / list_workflows / stats / contract` | Sorgu + sözleşme |

## Determinizm
- **DAG doğrulama:** DFS renklendirme ile döngü tespiti + eksik bağımlılık.
- **Topolojik sıra:** Kahn algoritması, bağımsızlar ada göre sıralı (kararlı/tekrarlanabilir).
- **Ready hesabı:** bir görev yalnız TÜM `depends_on` görevleri `completed` olunca `ready` olur; `requires_approval`
  ise `blocked_approval` (Madde 24).
- **Checkpoint/resume:** tamamlanan görevler kalıcı (SQLite) → `workflow_run` kaldığı yerden devam eder.
- **Rollback:** hedef görev + dolaylı ardılları `pending` (deterministik descendant kümesi).

## Executive köprüsü (yürütme domain'de DEĞİL)
`appservice.workflow_run`: `start` → döngüde `ready_tasks` → her ready görevin capability'sini **ConnectorManager**
ile yürüt → `complete_task`/`fail_task` (checkpoint). `blocked_approval` görevler `approve=True` ile onaylanır
(Madde 24). Capability'siz görev (salt-mantık) doğrudan tamamlanır. `connector_unavailable` → görev fail (workflow
durur; sonra resume/rollback mümkün).

## Invariantlar
- Görev grafı DAG'dir (döngü reddedilir).
- Görev yalnız bağımlılıkları completed olunca ready.
- Human-approval görevi onaysız çalışmaz (Madde 24).
- Checkpoint kalıcı → resume kaldığı yerden.
- Domain ConnectorManager çağırmaz (görev CapabilityIntent taşır; Executive yürütür).

## Bağımlılıklar (DI)
`WorkflowDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.workflow`). CLI `workflow`, HTTP
`/workflow`. Test: `tests/test_workflow_domain.py`.
