# Observability Domain (Faz 4 · Domain 13) — v1.0.0 · FROZEN

Sistemin **canlı telemetri** resmini toplar. EventBus'ı **PASİF** dinler (`subscribe_all`) — yan etki yok,
yalnız gözler. Her olay bir **olay-tipi sayacını** artırır ve telemetri halkasına yazılır. Özel metrikler
(counter/gauge) kaydedilebilir. **Deterministik SAĞLIK roll-up'ı** eşik tabanlıdır. Tek dinleyiciyle **tüm 12
domaini** kapsar (event-driven mimarinin meyvesi). Çekirdeğe dokunmaz.

## Public API (`ObservabilityDomain`)
| Operasyon | Açıklama |
|---|---|
| `record_metric(actor, name, value, kind)` | Özel gauge/counter kaydet (`evt:` öneki ayrılmış) |
| `incr(actor, name, by)` | Sayaç artır |
| `snapshot(actor)` | Tüm olay sayaçları + özel metrikler + toplamlar |
| `events(actor, type, limit)` | Son telemetri olayları |
| `health(actor)` | Deterministik sağlık: healthy / degraded / unhealthy |
| `stats` / `contract` | Observability + versioned sözleşme |

## Sağlık (dürüst, eşik tabanlı)
- **degraded**: LoopGuard bir devre açtıysa (`scheduler.job_disabled ≥ 1`) veya çökme tespit edildiyse
  (`scheduler.zombie_reaped ≥ 1`).
- **unhealthy**: birden çok devre açıldıysa (`disabled_jobs ≥ 3`).
- **healthy**: aksi hâlde. **Governance blokları ve guardrail kapıları SAĞLIKLI davranıştır** — unhealthy
  saymaz (sistem doğru çalışıyor demektir).

## Invariantlar
- **Pasif:** telemetri yan etki üretmez; yalnız dinler/toplar (kendi olayları tekrar sayılır, döngü yok).
- **Deterministik sağlık:** aynı sinyaller → aynı statü.
- **Süreklilik:** metrikler kalıcı (yeniden başlatmada geri yüklenir); olay halkası budanır.

## Yetki
Okuma: owner + Executive/Operations/Workflow/Communication. Metrik yazma: owner + Executive/Operations/Workflow.

## Production bileşenleri (placeholder YOK)
Model (TelemetryEvent) · Repository (SQLite write-through, metric + event ring) · Contract v1.0.0 · Events
(health_evaluated/metric_recorded) · Authorization · Validation · Error hiyerarşisi · Observability
(kendi metrikleri) · Config · Unit+Integration+Smoke (`tests/test_observability_domain.py`) · Docs.

## Bağımlılıklar (DI)
`ObservabilityDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.observability_domain`;
mevcut `mio.observability()` runtime metodu geriye-uyum için korunur) ve bus'a abone eder.

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
