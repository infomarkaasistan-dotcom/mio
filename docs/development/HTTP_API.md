# HTTP API — stdlib http.server adapter (Interface Katmanı #2)

> **HTTP yalnızca bir ADAPTER'dır.** Her istek `mio_core.appservice` (CLI ile **PAYLAŞILAN** sözleşme yüzeyi)
> üzerinden delege edilir — **iş mantığı KOPYALANMAZ** (Madde 15/16). Executive Core'a **framework bağımlılığı
> EKLENMEZ** (stdlib `http.server`). İstenirse FastAPI/Flask ileride **ayrı bir adapter paketi** olarak eklenebilir.

## Çalıştırma
```bash
python -m mio_core serve                          # 127.0.0.1:8080 (varsayılan)
python -m mio_core serve --host 0.0.0.0 --port 9000
# env ile: MIO_HTTP_HOST / MIO_HTTP_PORT / MIO_WORKSPACE  (adapter okur; ÇEKİRDEK okumaz)
```
Yerelde (py3.14 kırık): `uv run --python 3.12 python -m mio_core serve`.

## Uç noktalar
| Metod & Yol | Karşılık (appservice) |
|---|---|
| `GET /` | endpoint indeksi |
| `GET /health` | sağlık özeti |
| `GET /readiness` | hazırlık — **200 ready / 503 not-ready** |
| `GET /metrics` | tüm domain metrikleri |
| `GET /domains` | domain listesi |
| `GET /domains/{name}/contract` | domain sözleşmesi |
| `GET /domains/{name}/stats` | domain metrikleri |
| `GET /events?limit=N` | son olaylar |
| `POST /domains/{name}/{operation}` | operasyon çağrısı — **JSON gövde = kwargs** (`{"actor":"owner",...}`) |

### Örnek
```bash
curl localhost:8080/domains/iot/contract
curl -X POST localhost:8080/domains/iot/register_thing \
     -d '{"actor":"owner","name":"Kazan","kind":"sensor"}'
```

## Hata → HTTP statü eşlemesi (domain istisnaları)
Domainlerin kendi authz/validation'ı (Madde 24 vb.) **HTTP'de de yürürlükte**; istisnalar statüye çevrilir:
`UnauthorizedError→403` · `ValidationError→400` · `NotFoundError→404` · `TransitionError→409` · bilinmeyen→500 ·
yol yok→404 · gövde-dict-değil / özel-metod→400. Sunucu istisnada **çökmez**.

## Eşzamanlılık & güvenlik (dürüst kapsam)
- **Tek-thread'li `HTTPServer`** (bilinçli): repository eşzamanlılık sınırı (PLATFORM_HARDENING.md 'Eşzamanlılık
  bulgusu') nedeniyle istekler serileştirilir. Çok-thread sunum, persistence remediasyonu (thread-başına bağlantı)
  sonrasına ertelendi.
- **Varsayılan bağ 127.0.0.1** (yerel geliştirme). Reflektif `call` güçlüdür; **ağ-seviyesi kimlik doğrulama
  (token/mTLS) henüz YOK** — production'da API gateway / auth adapter gerekir (ayrı gelecek katman). Container'da
  `0.0.0.0` yalnız güvenli ağ + auth arkasında kullanılmalıdır.

## Mimari kanıt
`tests/test_http_api.py` (6): saf `route_request` eşlemesi + gerçek soket uçtan-uca + **CLI ile HTTP'nin AYNI
`appservice`'i kullandığı** (`test_http_and_cli_share_appservice`). Yani tek satır iş mantığı kopyalanmadı.
