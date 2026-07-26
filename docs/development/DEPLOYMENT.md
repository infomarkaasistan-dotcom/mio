# Deployment & Monitoring (Production Hardening #7)

> **Dürüstlük çerçevesi (ÖNCE OKU):** MIO çekirdeği **gömülebilir bir RUNTIME**'dır — **dahili HTTP/servis
> sunucusu YOKTUR**. Bu yüzden "production deployment" iki anlama gelir: (a) runtime'ı bir host süreç/servise
> **gömmek**, (b) bu repodaki **ops probe**'u sağlık/monitoring kancası olarak konuşlandırmak. Dışa açık bir
> **HTTP API katmanı ayrı, henüz yapılmamış bir çıktıdır** (bkz. AUTONOMOUS_STATE "alternatif yönler").
> Aşağıdakiler **çalışan artefaktlar**dır; **gerçek bir sunucuya deploy kullanıcının altyapı kararıdır** —
> bu ortamdan gerçek deploy YAPILMADI (yalnız artefakt + probe doğrulandı).

## Artefaktlar (bu repoda, çalışır)
| Artefakt | Ne işe yarar |
|---|---|
| `mio_core/ops.py` + `mio_core/__main__.py` | `python -m mio_core <cmd>` ops/monitoring probe |
| `Dockerfile` | Stdlib-only imaj + `HEALTHCHECK` = readiness probe |
| `.github/workflows/ci.yml` | CI (fitness→readiness→tam süit); deploy öncesi kapı |

## Ops probe (readiness / health / metrics)
```bash
# Readiness — hazırsa exit 0, değilse exit 1 (K8s readinessProbe / Docker HEALTHCHECK muadili)
python -m mio_core readiness --workspace /data/mio ; echo "exit=$?"

# Sağlık özeti (yetenek/diagnostics)
python -m mio_core health

# Birleşik metrics (tüm domain stats + event bus sağlığı) — monitoring scrape
python -m mio_core metrics
```
Her komut tek-satır JSON basar (`default=str`, `sort_keys`), makine-okur toplama için uygundur. `readiness`
**exit kodu** ile orkestratöre sinyal verir (0=ready, 1=not-ready).

## Container
```bash
docker build -t mio-executive-os .
docker run --rm -v mio_data:/data mio-executive-os readiness
# HEALTHCHECK otomatik readiness probe koşar; `docker inspect --format '{{.State.Health.Status}}'` ile görülür.
```
Kalıcı state `/data` hacmindedir (SQLite domain depoları + WAL). Yedekleme için `docs/development/
PLATFORM_HARDENING.md` → Recovery (hot-backup API / soğuk-kopya + WAL checkpoint).

## Monitoring önerisi (deterministik gözlem katmanı hazır)
- **Metrics:** `mio.metrics()` → domain-başına stats + event bus `subscriber_errors`. Periyodik scrape edip
  zaman-serisine yaz (host tarafı).
- **Health/Readiness:** `mio.readiness()` (deterministik self-check) + `mio.health()` (yetenek/diagnostics).
- **Structured logging:** `mio_core/platform/observability.StructuredFormatter` → tek-satır JSON log; sır
  anahtarları (`key/token/secret/...`) otomatik maskelenir (`.env` sızıntısına karşı).
- **Tracing:** `mio_core/platform/observability.Tracer` → nested span + `trace_id` correlation + süre; host
  akışına gömülür.

## Deploy öncesi kapılar (kanıt)
1. CI yeşil (fitness + readiness + tam süit; py3.10-3.12) — `github.com/.../actions`.
2. `python -m mio_core readiness` exit 0.
3. Load/Soak + Recovery süitleri yeşil (`tests/test_load_soak.py`, `tests/test_recovery.py`).

## Henüz YAPILMAYAN (dürüst kapsam)
- Dışa açık **HTTP/gRPC API** (domainleri servis olarak sunan katman).
- Gerçek bir **cluster/cloud deploy** + canlı monitoring stack (Prometheus/Grafana vb.) entegrasyonu.
- **Resilience** connector'lara sarma (gerçek adapter bağlanınca) ve **HA/replica** stratejisi.
Bunlar `PLATFORM_HARDENING.md` ve AUTONOMOUS_STATE'te kayıtlı sıradaki kalemlerdir. Deploy'un yeşil olması
**"artefakt + probe hazır"** demektir; tam **Production Ready** için yukarıdakiler gerekir
([[feedback_maturity_label_honesty]]).
