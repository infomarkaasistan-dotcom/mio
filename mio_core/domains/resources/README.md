# Resource & Runtime Domain (Constitution Faz 2 · Domain 19) — Maturity: STABLE

> Constitution refs: Madde 30 (Resource Awareness), Madde 11 (Hardware Operations başlangıç), Madde 16
> (küçük çekirdek). **Compliance: FULLY COMPLIANT (kapsam içi).**

**Resource Awareness**: GERÇEK kaynak snapshot'ı (probe) + **API/Token/Cost bütçe** takibi + **deterministik
darboğaz/yükseltme** analizi. Executive "doğru" kadar "verimli" çözümü de seçebilsin diye kaynakları sorgular
(`can_afford`, `bottlenecks`). Çekirdek hardware adaptörünü **sarar**; kendisi donanım/ağ erişimi yapmaz
(enjekte edilen `probe`).

## Public API (`ResourceRuntimeDomain`)
| Operasyon | Açıklama |
|---|---|
| `snapshot(actor)` | Anlık GERÇEK kaynak (CPU/RAM/GPU/Disk); eksik alan dürüstçe atlanır |
| `set_budget(actor, name, limit, unit)` | Bütçe tanımla (admin; API/token/cost) |
| `consume(actor, name, amount)` | Tüketim kaydet → kalan + aşım görünür |
| `can_afford(actor, name, amount)` | **Karar-öncesi** deterministik sığar-mı kontrolü |
| `reset_budget / budget_status` | Bütçe yönetimi + durum |
| `bottlenecks(actor)` | Deterministik darboğaz (RAM/CPU/Disk eşikleri) |
| `recommendations(actor)` | Deterministik yükseltme/optimizasyon önerileri |
| `stats / contract` | Observability + versioned sözleşme |

## Invariantlar
- **Uydurma yok:** snapshot yalnız probe'un verdiği gerçek veriden; eksik alan atlanır.
- **Deterministik:** bütçe tüketimi ve darboğaz analizi aynı girdi → aynı sonuç.
- **Görünür aşım:** bütçe aşımı event üretir; `can_afford` karar-öncesi kapıdır.

## Yetki
Okuma/snapshot/bottleneck: owner + Executive/Operations/Planning/Workflow/Engineering/Reasoning. Tüketim:
owner + Executive/Operations/Workflow/Execution. Bütçe yönetimi (set/reset): **admin** = owner + Executive +
Operations.

## Production bileşenleri (placeholder YOK)
Model (Budget) · Repository (SQLite: budget + snapshot history) · Contract v1.0.0 · Events (snapshot/budget_set/
budget_consumed/budget_exceeded/bottleneck) · Authorization (admin ayrımı) · Validation · Error hiyerarşisi ·
Observability (metrics+events) · Config · Unit+Integration+Smoke (`tests/test_resources_domain.py`) · Docs.

## Bağımlılıklar (DI)
`ResourceRuntimeDomain(repository, probe=Callable, bus, config)` — `runtime.boot()` bağlar (`mio.resources`);
probe = donanım keşfi + disk.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
