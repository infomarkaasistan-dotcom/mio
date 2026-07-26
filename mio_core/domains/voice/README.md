# Voice Domain (Faz 4 · Domain 30) — Maturity: STABLE

> Constitution refs: Madde 6/7 (dış sistem adapter üzerinden), Madde 8 (dürüstlük), Madde 16 (küçük çekirdek).
> **Compliance: FULLY COMPLIANT (kapsam içi).** Vision (Domain 29) ile aynı connector-delegation deseni.

Voice gerçek **STT/TTS** modeli gerektirir → deterministik **ORKESTRASYON**: audio asset registry + voice-iş
durum makinesi (pending→running→completed/failed/**no_connector**) + connector routing. Gerçek transcribe/
synthesize/diarize enjekte edilen **analyzer (adapter)**'a delege. **Analyzer yoksa `no_connector`** —
uydurma sonuç **YOK** (Madde 8). Çekirdek model çalıştırmaz.

## Public API (`VoiceDomain`)
| Operasyon | Açıklama |
|---|---|
| `register_analyzer(kind, fn, name)` | GERÇEK STT/TTS connector bağla (DI; transcribe/synthesize/diarize) |
| `register_asset(actor, uri, duration_sec, fmt)` | Audio asset kaydı |
| `transcribe(actor, asset_id)` | STT işi (asset gerekir) |
| `synthesize(actor, text)` | TTS işi (metin gerekir) |
| `diarize(actor, asset_id)` | Konuşmacı ayrımı |
| `get_job / list_jobs / connectors / stats / contract` | Sorgu + sözleşme |

## Invariantlar
- **Delege:** gerçek STT/TTS adapter'a gider; çekirdek model çalıştırmaz.
- **Dürüstlük (Madde 8):** analyzer yoksa `no_connector`; uydurma sonuç yok.
- **Determinizm:** durum makinesi + routing deterministik; connector hatası işe (`failed`) dönüşür.

## Yetki
Okuma: owner + Executive/Communication/Perception/Operations/Marketing/Research/Reasoning/Planning. Yazma:
owner + Executive/Communication/Perception/Operations.

## Production bileşenleri (placeholder YOK)
Model (AudioAsset/VoiceJob) · Repository (SQLite) · Contract v1.0.0 · Events (asset_registered/job_created/
completed/failed/no_connector) · Authorization · Validation · Error hiyerarşisi · Observability (metrics+events) ·
Config · Unit+Integration+Smoke (`tests/test_voice_domain.py`) · Docs.

## Bağımlılıklar (DI)
`VoiceDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.voice`). Gerçek STT/TTS analyzer'lar
sonradan `register_analyzer` ile bağlanır.

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL; gerçek STT/TTS bağlı değil
(`no_connector` = **dürüst** durum, placeholder değil). Bkz. `docs/development/MATURITY_AUDIT.md`.
