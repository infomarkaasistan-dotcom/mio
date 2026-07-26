"""MIO Core · Document Intelligence Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Deterministik doküman analizi + kural-tabanlı sınıflandırma + EXTRACTIVE özet (kaynak cümleler; uydurma yok).
LLM ancak soyut/abstractive özet için danışman olabilir — çekirdek deterministiktir. authz · validation ·
events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from . import analyzer
from .contract import CONTRACT_VERSION, DocEvents, document_contract
from .models import (
    DocConfig,
    DocType,
    Document,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import DocumentRepository

logger = logging.getLogger("mio.domain.document_intelligence")


class DocumentIntelligenceDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: DocumentRepository, *, bus=None,
                 config: Optional[DocConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or DocConfig()
        self._metrics = {"ingested": 0, "analyses": 0, "classifications": 0, "summaries": 0}

    # ------------------------------------------------------------------ #
    def ingest(self, actor: str, title: str, content: str, *, source: str = "") -> dict[str, Any]:
        """Dokümanı kaydeder + kural-tabanlı tür tespiti yapar."""
        self._authorize_writer(actor)
        title = self._require(title, "başlık")
        content = self._require(content, "içerik")
        doc_type = analyzer.classify(content)["doc_type"]
        doc = Document(title=title, content=content, doc_type=doc_type, source=source)
        self._repo.put(doc)
        self._metrics["ingested"] += 1
        self._emit(DocEvents.INGESTED, {"actor": actor, "id": doc.id, "doc_type": doc_type})
        return doc.to_dict()

    def analyze(self, actor: str, *, doc_id: Optional[str] = None,
                content: Optional[str] = None) -> dict[str, Any]:
        """Deterministik yapısal analiz (doc_id veya doğrudan content)."""
        self._authorize(actor)
        text = self._resolve_text(doc_id, content)
        report = analyzer.analyze(text, top_terms=self._cfg.top_terms,
                                  words_per_minute=self._cfg.words_per_minute)
        self._metrics["analyses"] += 1
        self._emit(DocEvents.ANALYZED, {"actor": actor, "words": report["words"]})
        return report

    def classify(self, actor: str, *, doc_id: Optional[str] = None,
                 content: Optional[str] = None) -> dict[str, Any]:
        self._authorize(actor)
        text = self._resolve_text(doc_id, content)
        result = analyzer.classify(text)
        self._metrics["classifications"] += 1
        self._emit(DocEvents.CLASSIFIED, {"actor": actor, "doc_type": result["doc_type"]})
        return result

    def summarize(self, actor: str, *, doc_id: Optional[str] = None, content: Optional[str] = None,
                  max_sentences: Optional[int] = None) -> dict[str, Any]:
        """EXTRACTIVE özet — kaynak cümlelerden (uydurma yok)."""
        self._authorize(actor)
        text = self._resolve_text(doc_id, content)
        n = int(self._cfg.summary_sentences if max_sentences is None else max_sentences)
        if n < 1:
            raise ValidationError("max_sentences >= 1 olmalı")
        summary = analyzer.summarize(text, max_sentences=n)
        self._metrics["summaries"] += 1
        self._emit(DocEvents.SUMMARIZED, {"actor": actor, "sentences": n})
        return {"summary": summary, "kind": "extractive", "max_sentences": n}

    # ------------------------------------------------------------------ #
    def get_document(self, actor: str, doc_id: str, *, include_content: bool = False) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_doc(doc_id).to_dict(include_content=include_content)

    def list_documents(self, actor: str, *, doc_type: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if doc_type is not None and doc_type not in DocType.ALL:
            raise ValidationError(f"Geçersiz tür: {doc_type}")
        return [d.to_dict() for d in self._repo.list(doc_type=doc_type)]

    def stats(self) -> dict[str, Any]:
        return {"documents": self._repo.count(),
                "invoices": self._repo.count(doc_type=DocType.INVOICE),
                "contracts": self._repo.count(doc_type=DocType.CONTRACT),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return document_contract()

    # ------------------------------------------------------------------ #
    def _resolve_text(self, doc_id: Optional[str], content: Optional[str]) -> str:
        if content is not None:
            return self._require(content, "içerik")
        if doc_id:
            return self._require_doc(doc_id).content
        raise ValidationError("doc_id veya content gerekli")

    def _require_doc(self, doc_id: str) -> Document:
        doc = self._repo.get(doc_id)
        if doc is None:
            raise NotFoundError(f"Doküman bulunamadı: {doc_id}")
        return doc

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' doküman erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' doküman yazımı için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
