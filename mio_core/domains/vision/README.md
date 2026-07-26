# Vision Domain (Faz 4 · Domain 29) — Maturity: STABLE

> Constitution refs: Madde 6/7 (dış sistem Operation Domain/adapter üzerinden), Madde 8 (dürüstlük — uydurma
> yok), Madde 16 (küçük çekirdek — model çekirdekte değil). **Compliance: FULLY COMPLIANT (kapsam içi).**

Vision gerçek **model/donanım** gerektirir → bu domain deterministik bir **ORKESTRASYON** katmanıdır: **asset
registry** + **analiz-işi durum makinesi** (pending→running→completed/failed/**no_connector**) + **connector
routing**. Gerçek OCR/nesne-tanıma/sınıflandırma enjekte edilen **analyzer (adapter)**'a delege edilir.
**Analyzer yoksa `no_connector`** döner — uydurma sonuç **YOK** (Madde 8). Çekirdek model çalıştırmaz.

## Public API (`VisionDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_analyzer(analysis, fn, name)` | GERÇEK connector bağla (DI; ocr/object_detection/classification/caption) |
| `register_asset(actor, uri, kind, width, height, description)` | Görsel asset kaydı |
| `analyze(actor, asset_id, analysis)` | İş oluştur → connector varsa çalıştır, yoksa `no_connector` |
| `get_job / list_jobs / list_assets` | İş/asset sorgu |
| `connectors(actor)` | Bağlı/eksik analiz türleri (ne yapılabilir, dürüst) |
| `stats / contract` | Observability + sözleşme |

## Invariantlar
- **Delege:** gerçek vision adapter'a gider; çekirdek model çalıştırmaz.
- **Dürüstlük (Madde 8):** analyzer yoksa `no_connector`; uydurma sonuç yok.
- **Determinizm:** durum makinesi + routing deterministik; connector hatası işe (`failed`) dönüşür, sistemi bozmaz.

## Yetki
Okuma: owner + Executive/Perception/Operations/Marketing/Research/Communication/Reasoning/Planning. Yazma
(asset/analyze): owner + Executive/Perception/Operations/Marketing.

## Production bileşenleri (placeholder YOK)
Model (Asset/VisionJob) · Repository (SQLite) · Contract v1.0.0 · Events (asset_registered/job_created/
completed/failed/no_connector) · Authorization · Validation · Error hiyerarşisi · Observability (metrics+events) ·
Config · Unit+Integration+Smoke (`tests/test_vision_domain.py`) · Docs.

## Bağımlılıklar (DI)
`VisionDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.vision`). Gerçek analyzer'lar sonradan
`register_analyzer` ile bağlanır (adapter).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek vision connector'ları henüz bağlı
değil (`no_connector`) — bu **dürüst** durumdur, placeholder değil. Bkz. `docs/development/MATURITY_AUDIT.md`.
