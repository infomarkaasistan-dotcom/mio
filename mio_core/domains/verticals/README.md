# Vertical Domain Brains (Faz 3 · Domain 11) — v1.0.0 · FROZEN

MIO'nun 8 **dikey alan beyni**: Business · Finance · Marketing · Sales · Product · Engineering · Security ·
Operations. Hepsi ortak bir üretim-kalite çekirdeği (`VerticalBrain`) paylaşır; davranış farkı **kodda değil
VERİDE** (`VerticalSpec`: odak bilgi alanı + odak etiketleri + guardrail'ler). Her beyin **tavsiye üretir,
KARAR VERMEZ** — `decision_authority = Executive` (kararlar E4'e gider). Purpose'a (sürdürülebilir gelir) en
yakın katman; MIO'yu iş üreten hâle getirir.

## Public API (her `VerticalBrain`, ör. `mio.verticals.finance`)
| Operasyon | Açıklama |
|---|---|
| `advise(actor, task, context_tags)` | Alan-spesifik **deterministik** tavsiye (Knowledge.apply + Reasoning izi) |
| `assess_action(actor, context_tags, user_approved)` | Alan **guardrail**'lerini uygular (allow / needs_approval / deny) |
| `history` / `explain(advice_id)` / `stats` / `contract` | Tavsiye izi + observability + sözleşme |

`mio.verticals`: registry — `.get(name)`, `.names()`, `mio.verticals["finance"]`, `mio.verticals.finance`, `.stats()`.

## Alan-spesifik guardrail'ler (Anayasa'yı deterministik uygular)
- **Finance:** `financial_commitment`/`new_expense` → **needs_approval** (Financial Rule; para harcamak çözüm değildir).
- **Security / Engineering:** `irreversible_action` → **needs_approval** (Executive onayı + geri-alınabilirlik / önce yedek).
- Diğerleri: guardrail'siz (yalnız tavsiye). `user_approved=True` needs_approval kapılarını geçer; `deny` geçilemez.

## Invariantlar
- **Karar vermez:** her tavsiye `decision_authority=Executive` taşır.
- **Deterministik:** tavsiye yalnız mevcut Knowledge/Reasoning'den türetilir (uydurma yok).
- **Guardrail'ler Anayasa'yı uygular** ve deterministiktir.

## Production bileşenleri (placeholder YOK)
Model (VerticalSpec/Advice) · Repository (SQLite write-through, tek tablo brain sütunlu) · Contract v1.0.0
(per-brain + layer) · Events (advised/guardrail_checked/guardrail_gated) · Authorization · Validation · Error
hiyerarşisi · Observability (metrics+log+events) · Config · Unit+Integration+Smoke
(`tests/test_verticals_domain.py`) · Docs.

## Bağımlılıklar (DI)
`VerticalBrains(knowledge: KnowledgeDomain, repository, reasoning=ReasoningDomain, bus, config)` —
`runtime.boot()` bağlar (`mio.verticals`).

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
