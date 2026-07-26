# Presentation Domain — Maturity: STABLE

> Constitution refs: **Katman ayrımı (domain ConnectorManager çağırmaz; yalnız niyet üretir)**, Madde 1 (LLM
> içerik danışmanı), Madde 3 (Executive tek karar verici), Madde 24 (yayın/gizlilik onay), Madde 8/16.
> **Compliance: FULLY COMPLIANT.**

**Sunum mantığını bilir; dış sistemleri (OBS/YouTube/Piper/Whisper/ElevenLabs/FFmpeg/Discord) İSİM olarak bile
bilmez.** 12 tür: speech · podcast · video · meeting · webinar · livestream · lesson · demo · screen_share ·
slides · avatar · conversation. Böylece sesli asistan / eğitim / webinar / satış sunumu / dijital avatar / AI
influencer aynı domain altında toplanır.

## Katman ayrımı (DEĞİŞMEZ)
```
Presentation Domain  →  CapabilityIntent (niyet)  →  Executive  →  ConnectorManager  →  Media Connector  →  Platform
   (sunum mantığı)        "konuş/yayınla/sun"          (karar)      (yalnız Executive'te)     (adapter)
```
Domain **connector'ı çağırmaz**; yalnız soyut niyet (`speech.synthesize`, `stream.start`, `slide.next`) üretir.
Niyetin **ne zaman/nasıl** yürütüleceğine EXECUTIVE karar verir. Dış sistem seçimi Executive + ConnectorManager
sorumluluğundadır. Executive köprüsü: `appservice.presentation_deliver` (ConnectorManager'ı yalnız burada çağırır).

## Public API (`PresentationDomain`)
| Operasyon | Açıklama |
|---|---|
| `create_script(actor, title, kind, goal, pace, segments, slides)` | Senaryo oluştur |
| `outline_to_script(actor, title, outline, kind)` | Outline → intro+bölümler+outro (deterministik) |
| `add_segment / add_slides` | Bölüm/slayt ekle |
| `plan_delivery(actor, script_id)` | Script → **CapabilityIntent dizisi** (YÜRÜTME YOK) |
| `intent(actor, target, request)` | Soyut hedef ("konuş"/"yayınla") → tek niyet |
| `start_session / advance_slide / end_session` | Oturum durum makinesi (slayt niyeti üretir) |
| `get_script / list_scripts / get_session / list_sessions / stats / contract` | Sorgu + sözleşme |

## Niyet (CapabilityIntent) — yürütme değil
`{capability, request, label, requires_approval}`. `plan_delivery` deterministik sıra üretir: canlı türde
`stream.start` (yüksek-risk) → her bölüm `speech.synthesize` → slaytlar `slide.next` → tür kapanışı
(`podcast.render`/`video.render`/`stream.stop`). Zaman: `estimate_seconds` (kelime/WPM, konuşma hızı).

## Güvenlik (Madde 24)
`HIGH_RISK_INTENTS` = stream.start/stop · podcast.publish · video.publish · screen.share · camera.capture ·
microphone.record → `requires_approval=True`. Executive köprüsü bunları onaysız YÜRÜTMEZ (ConnectorManager kapısı).

## Invariantlar
- Dış sistemleri isim olarak bile bilmez.
- ConnectorManager/connector ÇAĞIRMAZ; yalnız niyet üretir.
- Niyet yürütmesine Executive karar verir; ConnectorManager yalnız Executive'te.
- Akış/zaman/slayt DETERMİNİSTİK; LLM yalnız içerik (danışman).
- Yüksek-risk niyet onay ister (Madde 24).

## Bağımlılıklar (DI)
`PresentationDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.presentation`). Media connector'lar
Connector katmanında (Media kategorisi); domain onları bilmez. Test: `tests/test_presentation_domain.py`.
