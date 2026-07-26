# Conversational CLI — Doğal Dil Deneyimi (Unified Product Experience #1)

> **Bu YENİ bir mimari DEĞİL.** Mevcut Application Service Layer (`appservice`) üzerine bir **orkestrasyon
> katmanı**dır (`mio_core/conversational.py`). Kullanıcının doğal dil isteğini DETERMİNİSTİK bir intent'e çevirir
> ve **mevcut** appservice operasyonuna yönlendirir. İkinci bir workflow/task/memory/registry OLUŞTURMAZ — hepsini
> mevcut sistemler üzerinden yürütür (ürün bütünlüğü). LLM (Advisor) yalnız yorumlama için danışmandır; yönlendirme
> deterministiktir, karar Executive'in (Anayasa Madde 1/3).

## Pipeline
```
Kullanıcı (Türkçe) → Intent Analizi (deterministik) → Executive (yönlendirme) → mevcut appservice op → CEO yanıtı
```
Doğal dil **asla** keyfi operasyon çağırmaz; sabit bir intent kümesine eşlenir ve mevcut Application Service'e
delege edilir.

## İki mod, tek backend
- **Developer mode** — mevcut komutlar (`domains`, `call`, `workflow`, `present`, `chat`, `diagnose`...) aynen
  çalışır (backward-compat).
- **Conversational mode** — doğal Türkçe. REPL'de ilk sözcük bilinen bir komut DEĞİLSE otomatik doğal-dile gider;
  `ask <metin>` ile açıkça çağrılır.
- İkisi de **aynı** appservice'i yürütür (iş mantığı kopyalanmaz).

## Kullanım
```bash
python -m mio_core            # etkileşimli
MIO ❯ durum nedir             # → status → executive_summary
MIO ❯ sağlık kontrolü         # → diagnose
MIO ❯ sunum hazırla           # → present
MIO ❯ iş akışları neler       # → workflow
MIO ❯ devam et                # → önceki niyeti sürdürür (konuşma bağlamı)
MIO ❯ domains                 # geliştirici komutu (developer mode)
```
HTTP: `POST /converse {"text": "..."}` (aynı DTO — Dashboard/Mobile de kullanır).

## İntentler (deterministik)
`greeting · status · diagnose · hardware · models · present · conversation · workflow · connect · mcp · config ·
help · unknown`. Sıra özelden genele; ilk eşleşen kazanır.

## Türkçe sağlamlık
- **Diacritic-duyarsız:** `_TR_MAP` ile ı/ş/ğ/ü/ö/ç→ASCII → "yardım" == "yardim".
- **Kök/önek eşleşme:** kalıplar kapanış `\b` içermez → Türkçe sondan-eklemeli morfoloji ("mesaj"→"mesajları",
  "iş akış"→"iş akışları").
- **Konuşma bağlamı:** referans sözcükleri ('devam', 'bunu', 'geri dön') + son intent → süreklilik.

## LLM sınırı (Anayasa)
Bilinmeyen intent'te (yalnızca) Advisor'a **yorumlama** için sorulur (bağlı ise); Advisor **karar VERMEZ**, yalnız
"hangi eylemi kastetti" der. Yönlendirme ve yürütme deterministik/Executive kontrolündedir. Advisor yoksa yardım
önerisi döner (çökmez).

## Test / dürüstlük
`tests/test_conversational.py` (27): intent doğruluğu, diacritic-duyarsızlık, mevcut-servise-delege, konuşma
bağlamı, boş/anlamsız-çökmez, CLI/HTTP entegrasyonu + AYNI DTO. **Henüz YAPILMAYAN (dürüst kapsam):** tam
CEO-orchestration (intent→plan→delegate→execute→report zinciri), Business Workspace izolasyonu, onboarding — bunlar
Unified Product Experience'ın sonraki dilimleridir.
