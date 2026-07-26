"""MIO Core · Document Intelligence Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Deterministik doküman zekâsı: analiz (kelime/cümle/anahtar-terim), kural-tabanlı sınıflandırma, extractive
özet (frekans-skorlu, gerçek algoritma). OCR gerçek connector'a (adapter) bırakılır; çekirdek metin üzerinde
deterministik çalışır (uydurma yok)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocType:
    INVOICE = "invoice"
    CONTRACT = "contract"
    EMAIL = "email"
    REPORT = "report"
    CODE = "code"
    OTHER = "other"
    ALL = {INVOICE, CONTRACT, EMAIL, REPORT, CODE, OTHER}


class DocumentError(Exception):
    """Document Intelligence Domain temel hatası."""


class ValidationError(DocumentError):
    pass


class UnauthorizedError(DocumentError):
    pass


class NotFoundError(DocumentError):
    pass


@dataclass
class Document:
    title: str
    content: str
    doc_type: str = DocType.OTHER
    source: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        d = {"id": self.id, "title": self.title, "doc_type": self.doc_type, "source": self.source,
             "length": len(self.content), "created_at": self.created_at}
        if include_content:
            d["content"] = self.content
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Document":
        return cls(title=d["title"], content=d.get("content", ""), doc_type=d.get("doc_type", DocType.OTHER),
                   source=d.get("source", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class DocConfig:
    words_per_minute: int = 200        # okuma süresi tahmini
    summary_sentences: int = 3
    top_terms: int = 8
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Knowledge", "Research", "Operations", "Legal", "Finance",
        "Communication", "Reasoning", "Planning"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Knowledge", "Research", "Operations", "Legal"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "DocType", "Document", "DocConfig",
    "DocumentError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
