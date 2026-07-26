# MIO Documentation

MIO Executive OS — bağımsız bir **Cognitive Operating System**. Bu klasör platformun yönetişim ve mimari
dokümantasyonudur. Otorite sırası aşağıdaki gibidir; hiçbir alt doküman üsttekiyle çelişemez.

```
constitution/   → EN ÜST OTORİTE: Constitution v1.0 + Governance Extensions v1.0 (INDEX + CHANGELOG)
architecture/   → Reference Architecture (system-overview) + Reference Synthesis (3 proje)
adr/            → Architecture Decision Records (0001, 0002, 0003…)
domains/        → Domain Specifications index (15 FROZEN → mio_core/domains/*)
capabilities/   → Capability Contracts index
development/    → Development Memory (CURRENT_STATE / COMPLETED / NEXT_STEPS / BLOCKERS / SESSION_LOG)
                  + governance: MATURITY_AUDIT · TECHNICAL_DEBT · CONSTITUTION_COMPLIANCE
roadmap/        → PLATFORM_ROADMAP (40 domain · 5 faz)
```

## Yeni oturum / yeni geliştirici başlangıç prosedürü (Constitution Madde 17)
1. [`development/CURRENT_STATE.md`](./development/CURRENT_STATE.md) oku.
2. [`development/NEXT_STEPS.md`](./development/NEXT_STEPS.md) oku.
3. Son [`development/SESSION_LOG.md`](./development/SESSION_LOG.md) girdisini oku.
4. İlgili [`adr/`](./adr/) kararlarını kontrol et.
5. Mimariyi yeniden analiz etmek yerine **kaldığın yerden devam et.**

## En üst otorite
➡ [`constitution/CONSTITUTION_INDEX.md`](./constitution/CONSTITUTION_INDEX.md)
