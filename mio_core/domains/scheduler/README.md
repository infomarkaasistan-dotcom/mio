# Scheduler / Lifecycle Domain (Faz 4 · Domain 12) — v1.0.0 · FROZEN

MIO'nun **otonom döngü motoru** ve çalışma-zamanı sağlamlığı. `tick()` mantıksal saati 1 ilerletir ve vadesi
gelen işleri **kayıt sırasına göre deterministik** çalıştırır. **Duvar-saati thread YOK** — kontrolsüz süreç/
çökme riski yoktur (ilk oturumdaki "6 model → donma" sınıfı sorunun kök çözümü). Gerçek-zaman istenirse bir
sürücü periyodik olarak `tick()` çağırır (kenar adaptörü).

## Sağlamlık güvenceleri
- **LoopGuard:** bir iş ardışık `max_failures` kez hata verirse **devre açılır** (disabled); tick başına
  yürütme **tavanı** kontrolsüz iş-tetikler-iş patlamasını önler.
- **Zombie-guard:** çökmüş önceki süreçten kalan `running` koşular başlangıçta `reap_zombies()` ile toparlanır
  (koşu önce 'running' yazılır, sonra 'completed/failed' güncellenir → crash-consistency).
- **Yaşam-döngüsü:** `stopped`/`paused` durumda iş çalışmaz.

## Public API (`SchedulerDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_job(actor, name, handler, interval, one_shot, max_failures, run_at)` | İş kaydet (DI-time) |
| `tick(actor)` | Saati ilerlet + vadesi gelenleri çalıştır (deterministik, LoopGuard'lı) |
| `run_now(actor, name)` | Bir işi hemen çalıştır |
| `start/pause/resume/stop(actor)` | Yaşam-döngüsü geçişleri |
| `enable_job/disable_job/reap_zombies` | Devre + zombie yönetimi |
| `jobs / run_history / explain / stats / contract` | Sorgu + observability + sözleşme |

## Doğuştan öz-bakım işleri (runtime)
`memory_consolidation` (her 10 tick), `executive_review` (20), `learning_consolidation` (15) — yalnız `tick()`
çağrıldığında çalışır; otomatik arka-plan YOK (güvenli varsayılan).

## Yetki
owner + Executive/Operations/Workflow (okuma ve yönetim).

## Production bileşenleri (placeholder YOK)
Model (Job/ScheduleRun) · Repository (SQLite write-through, zombie-guard) · Contract v1.0.0 · Events (tick/
job_ran/job_disabled/job_registered/lifecycle/zombie_reaped) · Authorization · Validation · Error hiyerarşisi ·
Observability (metrics+log+events) · Config · Unit+Integration+Smoke (`tests/test_scheduler_domain.py`) · Docs.

## Bağımlılıklar (DI)
`SchedulerDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.scheduler`), zombie'leri toparlar,
öz-bakım işlerini kaydeder.

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
