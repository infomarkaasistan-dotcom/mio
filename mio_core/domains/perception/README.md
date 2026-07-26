# Perception Domain (Faz 2 · Domain 10) — v1.0.0 · FROZEN

MIO'nun **algı yüzeyi**: diyalog-dışı dış sinyalleri (olay/ölçüm/gözlem/uyarı) **DETERMİNİSTİK tipli
percept'lere** normalize eder ve bilişe yönlendirir. Communication konuşmayı, Perception **dünyayı sezmeyi**
kapsar — birlikte Faz 2 etkileşim döngüsünü tamamlar.

## Yönlendirme (deterministik)
- **OBSERVATION + subject → E5 belief** (inanç oluşumu; zıt kanıt çelişki olarak E5'te işaretlenir).
- **Her percept → Memory epizodik** (deneyim; best-effort, yetkili `Memory` sink kimliğiyle).
- **Yüksek belirginlik (salience ≥ eşik) → Attention** tetiği (event).
- Percept **her hâlükârda** kendi deposuna yazılır — yönlendirme başarısız olsa bile **kayıp yok**.

## Public API (`PerceptionDomain`)
| Operasyon | Açıklama |
|---|---|
| `perceive(actor, source, content, kind, subject, valence, salience, tags)` | Sinyali normalize et → yönlendir → kaydet |
| `recent(actor, limit, kind)` | Son percept'ler |
| `attention(actor)` | Dikkat gerektiren (yüksek belirginlik) percept'ler |
| `explain(actor, id)` / `stats` / `contract` | Sorgu + observability + sözleşme |

## Invariantlar
- **Deterministik normalizasyon:** türe göre varsayılan belirginlik (ALERT>EVENT>OBSERVATION>METRIC>SIGNAL).
- **Kanıt uydurulmaz:** yalnız gelen sinyalden türetilir.
- **Kayıpsız:** percept önce yönlendirilir sonra `routed` alanıyla kalıcılaştırılır.

## Yetki
Okuma: owner + Executive/Perception/Communication/Operations. Giriş (perceive): owner + Executive/Perception/Operations.

## Production bileşenleri (placeholder YOK)
Model (Percept) · Repository (SQLite write-through) · Contract v1.0.0 · Events (perceived/attention/routed) ·
Authorization · Validation · Error hiyerarşisi · Observability (metrics+log+events) · Config ·
Unit+Integration+Smoke (`tests/test_perception_domain.py`) · Docs.

## Bağımlılıklar (DI)
`PerceptionDomain(repository, memory=MemoryDomain, cognitive=CognitiveEngine, bus, config)` —
`runtime.boot()` bağlar (`mio.perception`). memory/cognitive opsiyoneldir (yönlendirme best-effort).

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
