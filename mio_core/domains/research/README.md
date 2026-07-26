# Research Domain (Faz 3 · Domain 21) — Maturity: STABLE

> Constitution refs: Madde 25 (Unified Knowledge — bilgi doğrulanmış/genellenebilir), Governance Extensions §9
> (LLM danışman), Madde 27 (açıklanabilirlik). **Compliance: FULLY COMPLIANT (kapsam içi).**

Deterministik araştırma: **soruşturma (inquiry)** + **bulgu (finding)** (kaynak/güvenilirlik/provenance) +
**DETERMİNİSTİK sentez**. Aynı ifadeyi bildiren **distinct kaynak sayısı = corroboration**; eşik üstü →
doğrulanmış; **tek-kaynak/doğrulanmamış** bulgular açıkça işaretlenir. LLM prose-sentezi danışmandır; yapısal
sentez ve doğrulama çekirdektedir. **Kanıt uydurulmaz** — yalnız girilen bulgulardan.

## Public API (`ResearchDomain`)
| Operasyon | Açıklama |
|---|---|
| `start_inquiry(actor, question)` | Araştırma sorusu aç |
| `add_finding(actor, inquiry_id, statement, source, credibility)` | Kaynaklı bulgu ekle |
| `verify_finding(actor, finding_id)` | Bulguyu doğrulanmış işaretle |
| `synthesize(actor, inquiry_id)` | **Deterministik sentez** + soruşturmayı 'synthesized' işaretle |
| `report(actor, inquiry_id)` | Salt-okunur sentez raporu |
| `list_inquiries / stats / contract` | Sorgu + observability + sözleşme |

## Deterministik sentez
- **corroboration:** distinct kaynak sayısı; `≥ corroboration_min` (varsayılan 2) veya doğrulanmış → **corroborated**.
- **confidence:** ortalama güvenilirlik ağırlığı + kaynak bonusu + doğrulama bonusu (deterministik).
- **single_source_unverified:** tek kaynaklı + doğrulanmamış bulgular açıkça listelenir.

## Invariantlar
- **Determinizm:** aynı bulgular → aynı sentez.
- **Uydurma yok:** yalnız girilen bulgulardan; tek-kaynak/doğrulanmamış işaretli.

## Yetki
Okuma/sentez: owner + Executive/Research/Knowledge/Reasoning/Planning/Marketing/Operations. Yazma:
owner + Executive/Research/Knowledge/Operations.

## Production bileşenleri (placeholder YOK)
Model (Inquiry/Finding) · Repository (SQLite) · Contract v1.0.0 · Events (inquiry_started/finding_added/
finding_verified/synthesized) · Authorization · Validation · Error hiyerarşisi · Observability (metrics+events) ·
Config · Unit+Integration+Smoke (`tests/test_research_domain.py`) · Docs.

## Bağımlılıklar (DI)
`ResearchDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.research`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
