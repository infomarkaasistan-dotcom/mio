# Goal Management Domain (Faz 1 · Domain 7) — v1.0.0 · FROZEN

E2 `GoalManager`'ı governance kabuğuyla **sarar** (çekirdeğe dokunmaz): uzun-vadeli hedef → milestone →
görev hiyerarşisi, **deterministik ilerleme** ve E1 (aktif hedef indeksi) senkron. Mutasyonlar GoalManager
üzerinden; okumalar paylaşılan GoalStore üzerinden — **tek doğruluk kaynağı** (Executive Domain ile aynı
hedef deposunu paylaşır).

## Public API (`GoalManagementDomain`)
| Operasyon | Açıklama |
|---|---|
| `define_goal(actor, text, horizon_days)` | Uzun-vadeli hedef tanımla (E1'e track) |
| `add_milestone(actor, goal_id, title, target_day_offset)` | Ufuk-içi milestone ekle |
| `add_task(actor, goal_id, milestone_id, description)` | Milestone'a görev ekle |
| `record_result(actor, task_id, status, result_summary)` | Sonucu yaz → otomatik ilerleme |
| `abandon(actor, goal_id)` | Meşru vazgeçiş (E1 aktif indeksten düşer) |
| `tree` / `progress` / `list_goals` / `stats` / `contract` | Sorgu + observability + sözleşme |

## Invariantlar
- **Deterministik ilerleme:** milestone tüm görevleri bitince tamamlanır; hedef tüm milestone'lar bitince.
- **E1 senkron:** aktif hedef indeksi tutarlı; meşru vazgeçiş desteklenir (Anayasa Madde 12).
- **Tek doğruluk kaynağı:** Executive Domain ve Goal Management aynı GoalStore'u paylaşır.

## Yetki
Okuma: owner + Executive/Planning/Goal/Reasoning/Learning. Yazma: owner + Executive/Planning/Goal.

## Production bileşenleri (placeholder YOK)
Model (çekirdek yeniden-kullanım) · Repository (paylaşılan SQLiteGoalStore) · Contract v1.0.0 · Events
(goal_defined/milestone_added/task_added/task_result/goal_completed/goal_abandoned) · Authorization ·
Validation (E2 ValueError → domain hata çevirimi) · Error hiyerarşisi · Observability (metrics+log+events) ·
Config · Unit+Integration+Smoke (`tests/test_goal_management_domain.py`) · Docs.

## Bağımlılıklar (DI)
`GoalManagementDomain(manager: GoalManager, store: GoalStore, bus, config)` — `runtime.boot()` bağlar
(`mio.goal_management`; ham `mio.goals` korunur).

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
