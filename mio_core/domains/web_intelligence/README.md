# Web Intelligence Domain (Faz 4 · Domain 32) — Maturity: STABLE

> Constitution refs: Madde 6/7 (dış sistem adapter üzerinden), Madde 8 (dürüstlük), Madde 24 (güvenli erişim),
> Madde 16 (küçük çekirdek). **Compliance: FULLY COMPLIANT (kapsam içi).**

Web erişimi **ağ** gerektirir → deterministik **ORKESTRASYON**: fetch/crawl/search iş durum makinesi
(pending→running→completed/failed/**no_connector**/**blocked**) + connector routing + **domain ALLOWLIST**
güvenliği. Gerçek ağ enjekte edilen **fetcher (adapter)**'a delege. **Fetcher yoksa `no_connector`** — uydurma
içerik **YOK** (Madde 8). Ağ **çekirdekte yok**.

## Public API (`WebIntelligenceDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_fetcher(kind, fn, name)` | GERÇEK ağ connector'ı bağla (DI; fetch/crawl/search) |
| `allow_host(actor, host)` | Allowlist'e host ekle (admin) |
| `fetch(actor, url)` / `crawl(actor, url, depth)` / `search(actor, query)` | İş oluştur → delege |
| `get_job / list_jobs / connectors / stats / contract` | Sorgu + sözleşme |

## Güvenlik (deterministik allowlist)
`allowed_hosts` **doluysa** yalnız listedeki host'lara `fetch`/`crawl` yapılır; aksi → **`blocked`** (event).
Boşsa tüm host'lara izin. `search` host gerektirmez. Host `urllib.parse` ile deterministik çıkarılır.

## Invariantlar
- **Delege:** gerçek ağ adapter'a gider; çekirdek ağ yapmaz.
- **Dürüstlük (Madde 8):** fetcher yoksa `no_connector`; uydurma içerik yok.
- **Güvenlik:** allowlist ihlali `blocked` (deterministik).

## Yetki
Okuma: owner + Executive/Research/Marketing/Operations/Knowledge/Reasoning/Planning/Perception. İş başlatma:
owner + Executive/Research/Operations. Allowlist: **admin** = owner + Executive + Security + Operations.

## Production bileşenleri (placeholder YOK)
Model (WebJob) · Repository (SQLite) · Contract v1.0.0 · Events (job_created/completed/failed/no_connector/
blocked) · Authorization (admin ayrımı) · Validation · Error hiyerarşisi · Observability (metrics+events) ·
Config · Unit+Integration+Smoke (`tests/test_web_intelligence_domain.py`) · Docs.

## Bağımlılıklar (DI)
`WebIntelligenceDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.web`). Gerçek fetcher'lar
sonradan `register_fetcher` ile bağlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek ağ connector'ı bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
