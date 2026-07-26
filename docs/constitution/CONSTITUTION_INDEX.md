# Constitution Index

MIO Platformu'nun **en üst seviye mimari otoritesi** ve yönetişim belgelerinin dizini. Bu klasördeki belgeler
projedeki diğer **tüm** teknik dokümanlardan üstündür.

## Canonical Belgeler (yürürlükteki sürümler)

| Belge | Sürüm | Durum | Açıklama |
|---|---|---|---|
| [MIO_ARCHITECTURAL_CONSTITUTION_v1.0.md](./MIO_ARCHITECTURAL_CONSTITUTION_v1.0.md) | 1.0.0 | RATIFIED | En üst mimari otorite (Madde 0–41). |
| [GOVERNANCE_EXTENSIONS_v1.0.md](./GOVERNANCE_EXTENSIONS_v1.0.md) | 1.0.0 | RATIFIED | Yönetişim uzantısı (§1–§10). |
| [CONSTITUTION_CHANGELOG.md](./CONSTITUTION_CHANGELOG.md) | — | Yaşayan | Sürüm geçmişi (eski sürümler silinmez). |

## Otorite Zinciri

```
MIO Architectural Constitution   (bu klasör — en üst otorite)
        ↓
Architecture Principles          (docs/architecture/)
        ↓
Reference Architecture           (docs/architecture/system-overview.md)
        ↓
ADR                              (docs/adr/)
        ↓
Domain Specifications            (docs/domains/)
        ↓
Capability Contracts             (docs/capabilities/)
        ↓
Implementation / Coding Standards
        ↓
Tests → Deployment → Operations
```

## Referans verme kuralı (zorunlu)

Bundan sonra oluşturulan **tüm** ADR, Domain Specification, Capability Contract ve teknik doküman bu
Constitution'a **referans vermelidir** (ilgili madde numarasıyla). Örnek başlık bloğu:

```
> Constitution refs: Madde 3 (Domain-First), Madde 16 (küçük çekirdek),
> Governance Extensions §4 (Bounded Context Isolation).
> Compliance: FULLY COMPLIANT
```

## İlgili yönetişim belgeleri

- **Development Memory:** [`../development/CURRENT_STATE.md`](../development/CURRENT_STATE.md) ·
  [`COMPLETED.md`](../development/COMPLETED.md) · [`NEXT_STEPS.md`](../development/NEXT_STEPS.md) ·
  [`BLOCKERS.md`](../development/BLOCKERS.md) · [`SESSION_LOG.md`](../development/SESSION_LOG.md)
- **Roadmap:** [`../roadmap/PLATFORM_ROADMAP.md`](../roadmap/PLATFORM_ROADMAP.md)
- **Reference synthesis (3 proje):** [`../architecture/REFERENCE_SYNTHESIS.md`](../architecture/REFERENCE_SYNTHESIS.md)
- **ADR dizini:** [`../adr/`](../adr/)
