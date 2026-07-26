# Media Generation Domain (Faz 4 · Domain 31) — Maturity: STABLE

> Constitution refs: Madde 6/7 (dış sistem adapter üzerinden), Madde 8 (dürüstlük), Madde 16 (küçük çekirdek).
> **Compliance: FULLY COMPLIANT (kapsam içi).** Vision/Voice ile aynı connector-delegation deseni.

Medya üretimi gerçek **model** gerektirir → deterministik **ORKESTRASYON**: üretim-iş durum makinesi
(pending→running→completed/failed/**no_connector**) + connector routing. Gerçek **image/video/audio** üretimi
enjekte edilen **generator (adapter)**'a delege. **Generator yoksa `no_connector`** — uydurma asset **YOK**
(Madde 8). Çekirdek model çalıştırmaz.

## Public API (`MediaGenerationDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_generator(kind, fn, name)` | GERÇEK üretim connector'ı bağla (DI; image_gen/video_gen/audio_gen) |
| `generate(actor, kind, prompt, params)` | Üretim işi → connector varsa çalıştır, yoksa `no_connector` |
| `get_job / list_jobs / connectors / stats / contract` | Sorgu + sözleşme |

## Invariantlar
- **Delege:** gerçek üretim modeli adapter'a gider; çekirdek model çalıştırmaz.
- **Dürüstlük (Madde 8):** generator yoksa `no_connector`; uydurma asset yok.
- **Determinizm:** durum makinesi + routing deterministik; connector hatası işe (`failed`) dönüşür.

## Yetki
Okuma: owner + Executive/Marketing/Communication/Operations/Product/Research/Reasoning/Planning. Üretim
(generate): owner + Executive/Marketing/Communication/Operations.

## Production bileşenleri (placeholder YOK)
Model (GenJob) · Repository (SQLite) · Contract v1.0.0 · Events (job_created/completed/failed/no_connector) ·
Authorization · Validation · Error hiyerarşisi · Observability (metrics+events) · Config · Unit+Integration+Smoke
(`tests/test_media_domain.py`) · Docs.

## Bağımlılıklar (DI)
`MediaGenerationDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.media`). Gerçek generator'lar
sonradan `register_generator` ile bağlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek üretim modeli bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
