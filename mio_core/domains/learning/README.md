# Learning Domain (Faz 1 · Domain 6) — v1.0.0 · FROZEN

Emergent öğrenme innate çekirdeğin **üzerine** biner. Sonuçları (beklenen↔gerçekleşen) gözler ve bilişsel
tabanı **DETERMİNİSTİK** günceller — LLM'e gerek yok:

1. **Bilgi güven revizyonu** — başarı → güven +, başarısızlık → güven − (`Knowledge.reinforce`).
2. **İnanç çürütme** — yanlışlanan inanç E5'te revizyona işaretlenir (`Cognitive.refute`).
3. **Heuristik emergence** — tekrar eden başarı, uygulanabilir yeni bir `decision_heuristic`'e dönüşür
   (`Knowledge.learn`). Böylece MIO deneyimden yeni, uygulanabilir bilgi üretir.

## Public API (`LearningDomain`)
| Operasyon | Açıklama |
|---|---|
| `record_outcome(actor, action, success, expected, actual, knowledge_id, belief_id, tags, lesson)` | Sonucu işle → deterministik etkiler |
| `consolidate(actor)` | Tekrar eden başarıdan heuristik emergence |
| `lessons(actor, limit)` / `history(actor, limit)` | Öğrenilen ders / olay geçmişi |
| `stats` / `contract` | Observability + versioned sözleşme |

## Invariantlar
- **Determinizm:** öğrenme kural tabanlıdır (sabit adımlar/eşikler), LLM'siz.
- **Innate koruması:** doktriner bilgi çürütülmez/silinmez; `reinforce` innate'e uygulanmaz (dürüstçe atlanır).
- **Emergence eşiği:** yalnız yeterli tekrar eden başarı + bağlam etiketi varsa yeni heuristik üretilir.

## Yetki
Okuma: owner + Executive/Learning/Reasoning/Knowledge/Memory. Yazma (record_outcome/consolidate):
owner + Executive/Learning.

## Production bileşenleri (placeholder YOK)
Model (LearningEvent) · Repository (SQLite write-through) · Contract v1.0.0 · Events (outcome_recorded/
knowledge_reinforced/belief_refuted/heuristic_emerged) · Authorization · Validation · Error hiyerarşisi ·
Observability (metrics+log+events) · Config · Unit+Integration+Smoke (`tests/test_learning_domain.py`) · Docs.

## Bağımlılıklar (DI)
`LearningDomain(repository, knowledge=KnowledgeDomain, cognitive=CognitiveEngine, bus, config)` —
`runtime.boot()` bağlar (`mio.learning`). knowledge/cognitive opsiyoneldir.

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
