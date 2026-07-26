# Reasoning Domain (Faz 1 · Domain 4) — v1.0.0 · FROZEN

Deterministik çıkarım katmanı. Bilgi (Knowledge.apply / retrieve) + inançlar (E5 Cognitive) + muhakeme
şablonlarını birleştirerek **açıklanabilir sonuç** üretir — LLM'e gerek yok. Kanıt uydurulmaz; yalnız
mevcut bilgi/inançtan derlenir. Her muhakeme denetlenebilir **iz (trace)** olarak kalıcılaştırılır.

Bounded context: Knowledge Domain'e **public sözleşme** üzerinden (`Reasoning` okuyucu kimliği) erişir;
E5 Cognitive'e yalnızca **okuma** yapar. Çekirdeğe dokunmaz.

## Public API (`ReasoningDomain`)
| Operasyon | Açıklama |
|---|---|
| `deduce(actor, context_tags)` | İleri-zincirleme: bağlama uygulanabilir bilgi → deterministik sonuç |
| `deliberate(actor, subject, context_tags, template)` | Şablonlu adım adım muhakeme; her adıma mevcut kanıt eşlenir |
| `consistency_report(actor)` | İnanç çelişkileri (E5) → tutarlılık denetimi |
| `explain(actor, trace_id)` | Kayıtlı muhakeme izini döner (açıklanabilirlik) |
| `history` / `stats` / `contract` | İz geçmişi + observability + versioned sözleşme |

## Invariantlar
- **Determinizm:** aynı girdi → aynı sonuç (rastgelelik yok, LLM yok).
- **Kanıt uydurulmaz:** çıkarım yalnız mevcut bilgi/inançtan derlenir.
- **Açıklanabilirlik:** her muhakeme iz olarak kalıcı (write-through SQLite, WAL).

## Yetki
owner + Executive/Reasoning/Planning/Knowledge/Learning.

## Production bileşenleri (placeholder YOK)
Model (ReasoningTrace) · Repository (SQLite write-through, denetim izi) · Contract v1.0.0 · Events
(deduced/deliberated/consistency_checked) · Authorization · Validation · Error hiyerarşisi · Observability
(metrics+log+events) · Config · Unit+Integration+Smoke (`tests/test_reasoning_domain.py`) · Docs.

## Bağımlılıklar (DI)
`ReasoningDomain(knowledge: KnowledgeDomain, repository, cognitive=CognitiveEngine, bus, config)` —
`runtime.boot()` bağlar (`mio.reasoning`).

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
