# Document Intelligence Domain (Faz 3 · Domain 22) — Maturity: STABLE

> Constitution refs: Madde 25 (Unified Knowledge), Governance Extensions §9 (LLM danışman), Madde 14
> (üretim-kalite). **Compliance: FULLY COMPLIANT (kapsam içi).**

Deterministik doküman zekâsı: **analiz** (kelime/cümle/anahtar-terim frekansı/okuma süresi/bölüm) +
**kural-tabanlı sınıflandırma** (invoice/contract/email/report/code/other) + **EXTRACTIVE özet**
(frekans-skorlu; kaynak cümlelerden — uydurma cümle yok). OCR gerçek connector'a (adapter) bırakılır; çekirdek
metin üzerinde deterministik çalışır. LLM ancak abstractive özet için danışman olabilir.

## Public API (`DocumentIntelligenceDomain`)
| Operasyon | Açıklama |
|---|---|
| `ingest(actor, title, content, source)` | Doküman kaydet + otomatik tür tespiti |
| `analyze(actor, doc_id/content)` | Yapısal analiz (kelime/cümle/anahtar-terim/okuma süresi/bölüm) |
| `classify(actor, doc_id/content)` | Kural-tabanlı tür + skorlar |
| `summarize(actor, doc_id/content, max_sentences)` | **Extractive** özet (kaynak cümleler) |
| `get_document / list_documents / stats / contract` | Sorgu + observability + sözleşme |

## Invariantlar
- **Determinizm:** aynı metin → aynı analiz/özet/sınıflandırma.
- **Extractive özet:** yalnız kaynak cümlelerden; uydurma cümle yok.
- **Kural-tabanlı sınıflandırma:** LLM'siz, şeffaf skorlar.

## Yetki
Okuma/analiz: owner + Executive/Knowledge/Research/Operations/Legal/Finance/Communication/Reasoning/Planning.
Yazma (ingest): owner + Executive/Knowledge/Research/Operations/Legal.

## Production bileşenleri (placeholder YOK)
Model (Document) · Analyzer (re, deterministik: analyze/classify/summarize) · Repository (SQLite) · Contract
v1.0.0 · Events (ingested/analyzed/classified/summarized) · Authorization · Validation · Error hiyerarşisi ·
Observability (metrics+events) · Config · Unit+Integration+Smoke (`tests/test_document_intelligence_domain.py`) · Docs.

## Bağımlılıklar (DI)
`DocumentIntelligenceDomain(repository, bus, config)` — `runtime.boot()` bağlar (`mio.document_intelligence`).

## Durum: **STABLE (Development Complete)** — üretim-doğrulanmış DEĞİL (bkz. `docs/development/MATURITY_AUDIT.md`).
