# MIO Interface Architecture — Anayasa (Constitution artefaktı)

> **Temel ilke:** MIO'nun TEK bir işletim sistemi vardır. CLI/HTTP/Desktop/Mobile/Voice **ayrı sistemler DEĞİL**;
> aynı OS'a farklı **arayüzlerdir**. Bu doküman bir Anayasa artefaktıdır; ihlali fitness test ile yakalanır
> (`tests/test_interface_architecture.py`).

## Katmanlar
```
                    MIO Executive Core (Executive + 43 Domain + Runtime)
                                   │
                    Application Service Layer  (mio_core/appservice.py)
                                   │
      ┌──────────────┬──────────────┬──────────────┬──────────────┐
     CLI         HTTP API      Desktop UI      Mobile UI       (VR/AR/Voice/...)
      └──────────────┴──────────────┴──────────────┴──────────────┘
                    Aynı Application Services · Aynı DTO'lar
```

## Altın Kural
**İş mantığı hiçbir arayüzün içinde OLMAZ.** Arayüzler yalnızca:
1. Girdi alır, 2. Application Service çağırır, 3. Çıktı **render** eder. Başka hiçbir şey.

## Application Service Layer (`mio_core/appservice.py`)
- Tek iş-mantığı-delegasyon noktası. Executive/Domain/Runtime'a delege eder; **kendi iş mantığı yoktur**.
- **Arayüz-agnostik DTO** döndürür (saf `dict`/`list`/`str` — JSON-serileştirilebilir). Aynı çağrı, her arayüzde
  **AYNI DTO**'yu verir: CLI metne, Dashboard karta, HTTP JSON'a, Mobile dokunuşa, Voice konuşmaya **render** eder.
- İş mantığı **yalnız bir kez** yürütülür (arayüzde değil, Service çağrısında).

## Arayüz Eşitliği
Her arayüz **eşit yeteneklidir**. Hiçbir arayüzün (Dashboard dahil) özel/dışlayıcı özelliği olamaz. Bir yetenek
varsa — platform kısıtı açıkça engellemedikçe — **her** arayüzden erişilebilir olmalıdır.

## Paylaşılan Runtime
Tüm arayüzler aynı Executive/Brains/Agents/Memory/Knowledge/Scheduler/Persistence/Connector Manager/MCP Manager/
Event Bus/Security/Monitoring ile konuşur. **Tek runtime vardır.**

## Arayüzler yalnız SUNUMDA farklılaşır
CLI=metin · Dashboard=grafik · HTTP=JSON · Mobile=dokunuş · Voice=konuşma. **Yürütme yolu her arayüzde
özdeştir.** Arayüzü değiştirmek sistemin davranışını **asla** değiştirmez.

## MIO'daki uygulama (mevcut durum)
- **`mio_core/appservice.py`** = Application Service Layer. DTO döndüren fonksiyonlar: `list_domains`,
  `domain_contract`, `domain_stats`, `metrics`, `readiness`, `health`, `events`, `call`, `connectors_overview`,
  `capabilities_catalog`, `execute_capability`, `prometheus_metrics`, `otlp_metrics`, `hardware_report`,
  `inference_analyze`, `inference_ensure_ready`, `diagnose`, `executive_summary`, `models_overview`.
- **`mio_core/cli.py`** = CLI arayüzü (metin render + startup sunumu). İş mantığı YOK → yalnız appservice.
- **`mio_core/http_api.py`** = HTTP arayüzü (JSON render). İş mantığı YOK → yalnız appservice.
- Gelecek Desktop/Mobile/Voice arayüzleri **aynı appservice**'i çağırır; iş mantığı kopyalanmaz.

## Fitness (otomatik denetim)
`tests/test_interface_architecture.py`: arayüz modülleri (cli/http_api) domain/repository iç modüllerini **import
etmez**; yalnız `appservice` (+ sunum) kullanır. Böylece "iş mantığı arayüzde yok" ilkesi her koşuda doğrulanır.
