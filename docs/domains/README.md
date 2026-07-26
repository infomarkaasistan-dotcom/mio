# Domain Specifications — Index

> Constitution refs: Madde 3 (Domain-First), Madde 4 (girdiği gün tam vatandaş), Governance Extensions §4
> (Bounded Context Isolation), §6 (Domain Lifecycle). Her Domain'in **kaynak-yanı** sözleşmesi ve README'si
> ilgili pakettedir: `mio_core/domains/<ad>/README.md` (FROZEN).

## Tamamlanan Domain'ler (15 · FROZEN v1.0.0)

| # | Domain | Paket | Contract |
|---|---|---|---|
| 1 | Executive | [`mio_core/domains/executive`](../../mio_core/domains/executive/README.md) | 1.0.0 |
| 2 | Memory | [`mio_core/domains/memory`](../../mio_core/domains/memory/README.md) | 1.0.0 |
| 3 | Knowledge | [`mio_core/domains/knowledge`](../../mio_core/domains/knowledge/README.md) | 1.0.0 |
| 4 | Reasoning | [`mio_core/domains/reasoning`](../../mio_core/domains/reasoning/README.md) | 1.0.0 |
| 5 | Planning | [`mio_core/domains/planning`](../../mio_core/domains/planning/README.md) | 1.0.0 |
| 6 | Learning | [`mio_core/domains/learning`](../../mio_core/domains/learning/README.md) | 1.0.0 |
| 7 | Goal Management | [`mio_core/domains/goal_management`](../../mio_core/domains/goal_management/README.md) | 1.0.0 |
| 8 | Communication | [`mio_core/domains/communication`](../../mio_core/domains/communication/README.md) | 1.0.0 |
| 9 | Execution | [`mio_core/domains/execution`](../../mio_core/domains/execution/README.md) | 1.0.0 |
| 10 | Perception | [`mio_core/domains/perception`](../../mio_core/domains/perception/README.md) | 1.0.0 |
| 11 | Vertical Domain Brains (8) | [`mio_core/domains/verticals`](../../mio_core/domains/verticals/README.md) | 1.0.0 |
| 12 | Scheduler/Lifecycle | [`mio_core/domains/scheduler`](../../mio_core/domains/scheduler/README.md) | 1.0.0 |
| 13 | Observability | [`mio_core/domains/observability`](../../mio_core/domains/observability/README.md) | 1.0.0 |
| 14 | Policy | [`mio_core/domains/policy`](../../mio_core/domains/policy/README.md) | 1.0.0 |
| 15 | Security | [`mio_core/domains/security`](../../mio_core/domains/security/README.md) | 1.0.0 |

## Her Domain'in içerdiği (Domain Geliştirme Kuralı)
model+kural · repository (SQLite write-through) · contract (versiyonlu) · events · authz · validation ·
observability · config · unit+integration+smoke test · README(FROZEN). **Placeholder/TODO/stub/mock YOK.**

Hedef Domain haritası (40 domain): [`../roadmap/PLATFORM_ROADMAP.md`](../roadmap/PLATFORM_ROADMAP.md).
