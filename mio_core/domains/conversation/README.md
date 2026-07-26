# Conversation Domain — Maturity: STABLE

> Constitution refs: **Katman ayrımı (domain ConnectorManager çağırmaz; doğrudan cevap göndermez; yalnız niyet
> üretir)**, Madde 3 (Executive tek karar verici — moderasyon önerir, karar vermez), Madde 24 (moderasyon/kitle
> onay), Madde 8/16. **Compliance: FULLY COMPLIANT.**

**Gerçek zamanlı insan etkileşiminin MANTIĞINI bilir; platformları (YouTube/Discord/Slack/Telegram/Teams/Twitch/
Kick/Instagram) İSİM olarak bile bilmez.** Mesaj alma/sınıflandırma, niyet analizi, bağlam, spam/flood/hakaret
tespiti, öncelik (VIP), moderasyon önerisi, sıra yönetimi, konu takibi, özet.

## Presentation Domain ile ayrım
- **Presentation:** "Ne anlatılacak, hangi sırayla, sunum nasıl ilerleyecek?" (konuşma akışı)
- **Conversation:** "İzleyiciler ne yazıyor, hangi sorular öncelikli, kime nasıl cevap verilecek?" (etkileşim)
Canlı yayında Presentation sunumu yürütür, Conversation sohbeti takip eder; **Executive** hangi anda soruya
geçileceğine karar verir. İkisi de aynı katman deseni: niyet üretir, Executive yürütür.

## Katman ayrımı (DEĞİŞMEZ)
```
Mesaj → Communication Connector → Event Bus → Executive → Conversation Domain → Executive → Advisor(gerekirse)
      → Executive → ConnectorManager → Communication Connector → Platform
```
Domain **doğrudan cevap GÖNDEREMEZ**; yalnız `ConversationIntent` (conversation.reply/delete/ban...) üretir.
Executive köprüsü: `appservice.conversation_reply/moderate` (ConnectorManager'ı yalnız burada çağırır).

## Public API (`ConversationDomain`)
| Operasyon | Açıklama |
|---|---|
| `receive(actor, user, text, platform_ref)` | Mesaj işle: sınıflandır + öncelik + moderasyon TESPİTİ (cevap yok) |
| `plan_reply(actor, msg_id, text, private)` | Cevap NİYETİ (conversation.reply) — yürütmez |
| `moderation_intent(actor, msg_id, action)` | Moderasyon niyeti (delete/timeout/ban/pin) — yüksek-risk onay |
| `queue(actor, limit)` | Cevap bekleyen mesajlar — öncelik sırası (VIP>high>normal>low) |
| `summarize(actor)` | Deterministik özet (mesaj/kullanıcı/niyet/moderasyon/bekleyen) |
| `set_vip / mark_answered / get_message / list_messages / get_user / list_users / stats / contract` | Sorgu |

## Moderasyon (TESPİT eder, KARAR VERMEZ — Madde 3)
`moderate_text` deterministik: **spam** (tekrar), **flood** (kısa sürede çok mesaj), **abuse** (hakaret sözlüğü),
**ad** (link/reklam). Bir **öneri** (allow/reply/ignore/delete/timeout) döndürür — Executive seçer. Yüksek-risk
öneri `requires_approval=True`.

## Güvenlik (Madde 24)
`HIGH_RISK_CONV_INTENTS` = conversation.delete/timeout/ban/broadcast/pin → onaysız YÜRÜTÜLMEZ (Executive köprüsü +
ConnectorManager çift kapı).

## Ölçek & çoklu platform
Domain platformu bilmez → aynı mantık YouTube/Discord/Slack/Telegram/Teams'te `conversation.receive`/`reply`
capability'leri üzerinden. 100K eşzamanlı için: mesajlar Event Bus üzerinden gelir, domain deterministik/durumsuz
işler, kalıcılık SQLite (ileride dağıtık kuyruk + Distributed Execution ile ölçeklenir). Gelecek: avatar/webinar/
eğitim/toplantı asistanı/moderatör/çok-dilli — capability-tabanlı, yeni connector yeterli.

## Bağımlılıklar (DI)
`ConversationDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.conversation`). Test:
`tests/test_conversation_domain.py`.
