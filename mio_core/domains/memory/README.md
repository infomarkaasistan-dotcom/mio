# Memory Domain (Faz 1 · Domain 2) — v1.0.0 · FROZEN

WM · STM · LTM · Episodic · Semantic · Procedural bellek + deterministik yaşam-döngüsü. Bounded context,
kendi SQLite repository'si; çekirdeğe eklenmez.

## Public API (`MemoryDomain`)
| Operasyon | Açıklama |
|---|---|
| `remember(actor, content, mtype, importance, tags, source)` | Belleğe yaz |
| `note_working(actor, content)` | Çalışma belleğine ekle (sınırlı, en zayıfı çıkarır) |
| `recall(actor, query, mtype, limit)` | Deterministik geri çağırma + pekiştirme |
| `working_set(actor)` | Aktif WM içeriği |
| `consolidate(actor)` | STM→LTM, episodic→semantic, çürüme, buda |
| `forget(actor, memory_id)` | Sil |
| `stats()` / `contract()` | Observability + versioned sözleşme |

## Yaşam-döngüsü (deterministik, LLM-siz)
- **WM sınırı** 7±2 → dolunca en zayıf/eski çıkar (event `working_evicted`).
- **Konsolidasyon:** STM importance≥eşik → LTM; aynı etiket ≥N epizotta → Semantic örüntü.
- **Çürüme + buda:** durable olmayan (STM/episodic) güç zamanla azalır, eşiğin altı budanır. Durable
  (LTM/Semantic/Procedural) korunur.

## Production bileşenleri (placeholder YOK)
Model+kural · Repository (SQLite kalıcı) · Contract v1.0.0 · Events (stored/recalled/consolidated/
forgotten/working_evicted) · Authorization (`MemoryConfig`) · Validation · Error hiyerarşisi · Observability
(metrics+log+events) · Config · Unit+Integration+Smoke test (`tests/test_memory_domain.py`) · Docs.

## Bağımlılıklar (DI)
`MemoryDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.memory`).

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
