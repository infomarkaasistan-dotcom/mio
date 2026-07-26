# Communication Domain (Faz 2 · Domain 8) — v1.0.0 · FROZEN

MIO'nun **diyalog yüzeyi**: çok-turlu, kalıcı konuşmalar + **DETERMİNİSTİK niyet sınıflandırma** + yanıt
kompozisyonu. LLM **yalnızca opsiyonel bir danışmandır** (doğal ifade için); erişilemezse domain
deterministik yollarla (kayıtlı handler / dürüst geri-dönüş) çalışmaya devam eder. Communication **karar
vermez** — niyeti çekirdeğe yönlendirir, cevabı derler.

## Yanıt kaynağı önceliği (deterministik)
1. **HANDLER** — niyete kayıtlı çekirdek handler'ı (ör. STATUS→öz-model, QUERY_KNOWLEDGE→Knowledge.what_do_i_know,
   GOAL→Goal Management, PLAN→Planning). LLM'siz gerçek cevap.
2. **ADVISOR** — opsiyonel LLM (yalnız Tool Orchestrator üzerinden). Bağlı değilse atlanır.
3. **FALLBACK** — dürüst geri-dönüş ("bunu şu an yanıtlayamıyorum"). Uydurma yok.

## Public API (`CommunicationDomain`)
| Operasyon | Açıklama |
|---|---|
| `converse(actor, text, conversation_id)` | Turu işle: niyet → yanıt (handler→advisor→fallback) → kaydet |
| `classify(text)` | Deterministik niyet (kural tabanlı; aynı girdi → aynı niyet) |
| `register_handler(intent, fn)` | Niyet için çekirdek handler DI (kompozisyon-zamanı) |
| `history` / `conversations` / `stats` / `contract` | Geçmiş + observability + sözleşme |

## Invariantlar
- **Niyet sınıflandırma deterministiktir** (LLM'siz, kural tabanlı).
- **LLM opsiyoneldir**: yokluğunda dürüst geri-dönüş; MIO çalışmaya devam eder.
- **Karar üretmez**: iş kararları Executive/E4'e aittir.

## Yetki
owner + Communication + Executive. Handler'lar okuma için `ctx["actor"]` kimliğini kullanır (paylaşılan yetki).

## Production bileşenleri (placeholder YOK)
Model (Conversation/Turn/Intent) · Repository (SQLite write-through) · Contract v1.0.0 · Events
(turn_received/intent_classified/replied) · Authorization · Validation · Error hiyerarşisi · Observability
(metrics+log+events) · Config · Unit+Integration+Smoke (`tests/test_communication_domain.py`) · Docs.

## Bağımlılıklar (DI)
`CommunicationDomain(repository, advisor=callable|None, bus, config)` — `runtime.boot()` bağlar
(`mio.communication`) ve gerçek handler'ları (STATUS/QUERY_KNOWLEDGE/GOAL/PLAN) + LLM advisor'ı kaydeder.

## Durum: **FROZEN (geliştirme tamamlandı)** · **Maturity: STABLE** — üretim-doğrulanmış DEĞİL (resilience/CI/yük/ops eksik; bkz. `docs/development/MATURITY_AUDIT.md`).
