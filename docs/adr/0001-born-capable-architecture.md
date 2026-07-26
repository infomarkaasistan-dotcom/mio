# ADR-0001 — Born Capable Architecture

- **Durum:** Kabul edildi (2026-07-24). Çekirdek mimari kararı — özellik değil.
- **Etki:** MIO Core'un doğuş felsefesi. Sonraki tüm geliştirmeler (Domain Brain'ler, Tool Orchestrator,
  MCP Hub) bu karara göre ilerler.

## Bağlam

Önceki yaklaşımda MIO **sıfır bilgi, sıfır deneyim, sıfır yetenekle** doğuyordu (emergent-boş). Bu uzun
vadede yanlıştır: böyle bir sistem kendi yeteneklerini tanımaz, temel işletme bilgisine sahip olmaz, her
problemi sıfırdan çözer, gereğinden fazla LLM'e bağımlı kalır, aynı hataları tekrarlar ve ilk açılıştan
itibaren kısır döngülere girer. Bu, "AI CEO / uzun yıllar yaşayacak bilişsel işletim sistemi" vizyonuyla
çelişir. MIO bir sohbet LLM'i değildir; **doğduğu anda çalışmaya hazır olmalıdır.**

## Karar

**MIO boş doğmaz; EĞİTİLMİŞ BİR BAŞLANGIÇ ÇEKİRDEĞİYLE (yetenekli) doğar.** Amaç "her şeyi bilmek" değil;
kendini tanıyan, araçlarını bilen, temel bilgiye sahip, çalışmaya hazır doğmaktır. Bilgi üç katmandır:

**1. Doğuştan Gelen (innate) — sistemle birlikte gelir:**
Constitution · Core · Executive Brain · Domain Brain'ler · World Knowledge · Business Knowledge (işletme/
pazarlama/satış/finans/yazılım geliştirme) · Strategy Knowledge · Tool Orchestrator · MCP Hub · Capability
Model. *Bu bilgi DENEYİM DEĞİL; eğitilmiş başlangıç çekirdeğidir.* MIO kendi mimarisini, sınırlarını,
hedeflerini ve yeteneklerini doğuştan bilir.

**2. Kurulum Sırasında Keşfedilen (discovered) — ilk açılışta:**
Aktif MCP'ler · API anahtarları · yerel servisler · çalışan modeller · donanım özellikleri · bağlı sistemler.
İlk açılışta MIO tüm MCP'leri **otomatik keşfeder**, hangilerinin aktif olduğunu belirler ve **Capability
Registry** oluşturur. MIO o andan itibaren "hangi araçlara sahibim / neleri yapabilirim / neleri yapamam"
sorularının cevabını bilir.

**3. Yaşayarak Öğrenilen (learned) — zamanla:**
Kullanıcı tercihleri · deneyimler · başarılar · başarısızlıklar · iş stratejileri · gelir optimizasyonu ·
karar geçmişi. (MIO Core'da bu katman zaten var: E1 DecisionLedger + Lessons + öğrenme zinciri.)

## Bağlayıcı kurallar

- **Domain Brain'ler doğuştan gelir** (emergent-doğuş değil) — sistemin doğal parçaları.
- **Tool Orchestrator + MCP Hub doğuştan gelir.** Desteklenen tüm MCP tanımları sistemle gelir.
- **Hiçbir Brain doğrudan 3. taraf API kullanmaz.** Tüm dış-dünya erişimi YALNIZCA Tool Orchestrator
  üzerinden, tercihen MCP standardıyla. (LLM de dahil: X4 Model Gateway bir Tool/danışmandır — ADR-0000 /
  çekirdek ilke: LLM asla beyin değil.)
- **Capability Model doğuştan; Capability Registry kurulumda üretilir.**

## MIO Core ile uyum (bu ADR mevcut çekirdeği BOZMAZ)

- **E1** zaten tohumlanabilir: `ensure_identity` + `set_mission` = kimlik/misyon doğuştan. Innate World/
  Business/Strategy knowledge → E1 `Lesson`'ları (source="innate") + E5 innate `Belief`'leri olarak tohumlanır.
- **E5 Cognitive Engine** `born_with(...)` ile innate inançlarla doğar (bu ADR ile birlikte uygulanıyor).
- **Tool Orchestrator / MCP Hub / Capability Registry / Domain Brain'ler** → Execution + Infrastructure
  katmanlarında, Core tamamlandıktan sonra bu ADR'ye göre tasarlanacak YENİ bileşenlerdir. Model Gateway (X4)
  ve Capability Registry (I) bu işin çekirdeğidir.

## Sonuçlar

- (+) MIO doğduğu an kendini/araçlarını/temel bilgiyi bilir → LLM'e aşırı bağımlılık ve kısır döngü azalır.
- (+) Emergent öğrenme YOK OLMAZ; innate çekirdeğin ÜSTÜNE gerçek deneyim ve kullanıcıya-özgü bilgi eklenir.
- (−) Innate bilgi bir "başlangıç tohumu" olarak bakımı gerektirir (güncel tutulmalı); deneyim değil, veri.
- **Eski "sıfır iş bilgisiyle doğ" ilkesi (MIO Beyin Madde IV/V) MIO Executive OS için GEÇERSİZDİR.**
