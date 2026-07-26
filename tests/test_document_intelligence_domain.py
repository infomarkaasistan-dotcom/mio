"""MIO Core · Document Intelligence Domain (Faz 3 · Domain 22) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek deterministik analizör (stdlib re) + SQLite üzerinden. Analiz/sınıflandırma/
extractive özet determinizmi, doküman yaşam-döngüsü, authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.document_intelligence import (
    DocEvents,
    DocType,
    DocumentIntelligenceDomain,
    DocumentRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    analyzer,
)
from mio_core.events import EventBus

_INVOICE = "FATURA No: 123\nTutar: 1000 TL\nKDV: 180 TL\nÖdeme: banka havalesi\nToplam tutar 1180 TL."
_REPORT = ("Bu rapor pazar analizini özetler. Analiz bulgularına göre talep artıyor. "
           "Rakip fiyatları düşürdü. Sonuç olarak büyüme fırsatı var. Rapor sonuç bölümü değerlendirme içerir. "
           "Talep artışı sürdürülebilir görünüyor.")


def _build():
    repo = DocumentRepository(":memory:")
    bus = EventBus(record=True)
    dom = DocumentIntelligenceDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def di():
    return _build()


# ---- UNIT: deterministik analizör ----
def test_analyzer_deterministic():
    assert analyzer.analyze(_REPORT) == analyzer.analyze(_REPORT)         # determinizm
    a = analyzer.analyze(_REPORT)
    assert a["words"] > 0 and a["sentences"] >= 5 and a["top_terms"]


def test_classify_rules():
    assert analyzer.classify(_INVOICE)["doc_type"] == DocType.INVOICE
    assert analyzer.classify(_REPORT)["doc_type"] == DocType.REPORT
    assert analyzer.classify("def f():\n return 1\nimport os")["doc_type"] == DocType.CODE
    assert analyzer.classify("rastgele metin xyz")["doc_type"] == DocType.OTHER


def test_summarize_is_extractive():
    summ = analyzer.summarize(_REPORT, max_sentences=2)
    # extractive: özet cümleleri kaynakta bulunmalı (uydurma yok)
    src_sentences = [s.strip() for s in _REPORT.replace("\n", " ").split(".") if s.strip()]
    for part in summ.split("."):
        p = part.strip()
        if p:
            assert any(p in s or s in p for s in src_sentences)
    assert analyzer.summarize(_REPORT, max_sentences=2) == analyzer.summarize(_REPORT, max_sentences=2)


# ---- INTEGRATION: ingest + tür tespiti + authorization ----
def test_ingest_and_authz(di):
    d, _r, bus = di
    doc = d.ingest("owner", "Fatura Nisan", _INVOICE)
    assert doc["doc_type"] == DocType.INVOICE
    assert d.list_documents("owner", doc_type=DocType.INVOICE)[0]["id"] == doc["id"]
    with pytest.raises(ValidationError):
        d.ingest("owner", "boş", "  ")
    with pytest.raises(UnauthorizedError):
        d.ingest("Reasoning", "x", "y")                    # reader ama writer değil
    with pytest.raises(UnauthorizedError):
        d.analyze("yabanci", content="x")
    assert any(e["type"] == DocEvents.INGESTED for e in bus.history())


# ---- INTEGRATION: analyze/summarize doc_id ile ----
def test_analyze_summarize_by_id(di):
    d, _r, _b = di
    doc = d.ingest("owner", "Rapor", _REPORT)
    a = d.analyze("owner", doc_id=doc["id"])
    assert a["words"] > 0
    s = d.summarize("owner", doc_id=doc["id"], max_sentences=2)
    assert s["kind"] == "extractive" and s["summary"]
    with pytest.raises(NotFoundError):
        d.analyze("owner", doc_id="yok")
    with pytest.raises(ValidationError):
        d.analyze("owner")                                 # ne doc_id ne content
    with pytest.raises(ValidationError):
        d.summarize("owner", content=_REPORT, max_sentences=0)


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(di):
    d, _r, _b = di
    d.ingest("owner", "F", _INVOICE)
    d.analyze("owner", content=_REPORT)
    s = d.stats()
    assert s["documents"] == 1 and s["invoices"] == 1 and s["analyses"] >= 1
    assert s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "document_intelligence" and "summarize" in c["operations"]


# ---- SMOKE: boot() → uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    doc = mio.document_intelligence.ingest("owner", "Sözleşme", "Bu sözleşme taraflar arasında madde 1 hüküm içerir. İmza gerekli.")
    assert doc["doc_type"] == DocType.CONTRACT
    summ = mio.document_intelligence.summarize("owner", doc_id=doc["id"])
    assert summ["kind"] == "extractive"
    assert mio.document_intelligence.contract()["version"] == "1.0.0"
    mio.close()
