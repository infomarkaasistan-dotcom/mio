"""MIO Core · Document Intelligence Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class DocEvents:
    INGESTED = "document.ingested"
    ANALYZED = "document.analyzed"
    CLASSIFIED = "document.classified"
    SUMMARIZED = "document.summarized"


OPERATIONS = ("ingest", "analyze", "classify", "summarize", "get_document", "list_documents", "stats")


def document_contract() -> dict[str, Any]:
    return {
        "domain": "document_intelligence",
        "version": CONTRACT_VERSION,
        "description": "Deterministik doküman zekâsı: analiz + kural-tabanlı sınıflandırma + extractive özet "
                       "(frekans-skorlu). OCR gerçek connector'a bırakılır; çekirdek metinde deterministiktir.",
        "operations": list(OPERATIONS),
        "events": [DocEvents.INGESTED, DocEvents.ANALYZED, DocEvents.CLASSIFIED, DocEvents.SUMMARIZED],
        "doc_types": ["invoice", "contract", "email", "report", "code", "other"],
        "invariants": ["analiz/özet/sınıflandırma deterministiktir (aynı metin → aynı sonuç)",
                       "özet EXTRACTIVE'dir (kaynak cümleler; uydurma cümle yok)",
                       "sınıflandırma kural-tabanlıdır (LLM'siz)"],
    }
