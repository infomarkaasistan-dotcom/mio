# Knowledge Domain (Faz 1 · Domain 3) — v1.0.0 · FROZEN

Tipli bilginin (Belief · Rule · Concept · Pattern · Principle · Mental Model · Reasoning Template ·
Decision Heuristic) governance altında yönetimi. Innate `KnowledgeBase`'i **sarar** (çekirdeğe dokunmaz) ve
yaşayan bilgiyi kendi SQLite deposunda **write-through** kalıcılaştırır.

MIO'nun ayırt edici gücü burada: bilgi *okunmaz, KULLANILIR* — `apply()` bir bağlama uygulanabilir bilgiyi
(Rule/Pattern/Heuristic) değerlendirip **deterministik öneri üretir** (LLM'e gerek yok).

## Public API (`KnowledgeDomain`)
| Operasyon | Açıklama |
|---|---|
| `learn(actor, LearnCommand/dict/**kw)` | Yaşayan bilgi öğren (write-through kalıcı) |
| `what_do_i_know(actor, query, limit)` | Deterministik geri getirme (uydurma yok) |
| `apply(actor, context_tags)` | Bağlama uygula → **deterministik öneriler** |
| `reinforce(actor, id, delta)` | Güven revizyonu (belief revision), yaşayan bilgi |
| `forget(actor, id)` | Unut (yalnızca yaşayan bilgi) |
| `list_knowledge` / `stats` / `contract` | Sorgu + observability + versioned sözleşme |

## Invariantlar
- **Innate bilgi doktrinerdir:** silinemez, güveni değiştirilemez (`ImmutableKnowledgeError`).
- **apply deterministiktir:** aynı bağlam → aynı öneriler; LLM'den bağımsız.
- **Yaşayan bilgi write-through kalıcıdır:** öğren/pekiştir/unut anında SQLite'a yazılır (WAL, çöküşe dayanıklı).
- Uygulanabilir tip (Rule/Pattern/Heuristic) `when` + `then` zorunlu kılar.

## Yetki (authorization)
Okuma/uygulama: owner + Executive/Knowledge/Learning/Reasoning/Planning/Memory. Yazma (learn/reinforce/
forget): owner + Knowledge/Learning.

## Production bileşenleri (placeholder YOK)
Model (çekirdek tip yeniden-kullanımı) · Repository (SQLite write-through) · Contract v1.0.0 · Events
(learned/retrieved/applied/reinforced/forgotten) · Authorization · Validation · Error hiyerarşisi ·
Observability (metrics+log+events) · Config · Unit+Integration+Smoke (`tests/test_knowledge_domain.py`) · Docs.

## Bağımlılıklar (DI)
`KnowledgeDomain(base: KnowledgeBase, repository, bus, config)` — `runtime.boot()` bağlar (`mio.knowledge_domain`;
ham `mio.knowledge` base'i geriye-uyum için korunur). Çekirdek `KnowledgeBase`'e yalnızca additive `remove()`
eklendi (backward-compatible).

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
