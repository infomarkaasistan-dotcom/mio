"""MIO Core · Document Intelligence · Analizör — DETERMİNİSTİK, stdlib-only (re), LLM-BAĞIMSIZ.

Metin analizi + kural-tabanlı sınıflandırma + extractive özet (frekans-skorlu). Aynı metin → aynı sonuç."""

from __future__ import annotations

import re
from typing import Any

from .models import DocType

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)               # harf dizileri (rakam/altçizgi hariç)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

# Küçük TR+EN stopword kümesi (deterministik; anahtar-terim/özet için gürültü azaltır)
_STOP = {
    "ve", "ile", "bir", "bu", "şu", "o", "da", "de", "için", "gibi", "ama", "ya", "veya", "ki", "mi",
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "be", "as", "at", "by",
    "with", "that", "this", "it", "was", "were", "from", "но", "çok", "daha", "en", "her", "olan",
}

# Kural-tabanlı sınıflandırma desenleri (deterministik)
_CLASS_HINTS = {
    DocType.INVOICE: ("fatura", "invoice", "kdv", "tutar", "ödeme", "total", "vergi", "birim fiyat"),
    DocType.CONTRACT: ("sözleşme", "contract", "taraflar", "hüküm", "madde", "imza", "yükümlülük"),
    DocType.EMAIL: ("kimden", "from:", "to:", "subject:", "konu:", "saygılar", "merhaba", "cc:"),
    DocType.REPORT: ("rapor", "report", "özet", "sonuç", "analiz", "bulgular", "değerlendirme"),
    DocType.CODE: ("def ", "class ", "import ", "function", "return ", "public ", "const ", "};"),
}


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "")]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s.strip()]


def term_frequencies(text: str, *, top: int = 8) -> list[tuple[str, int]]:
    freq: dict[str, int] = {}
    for w in _tokens(text):
        if len(w) > 2 and w not in _STOP:
            freq[w] = freq.get(w, 0) + 1
    # deterministik sıralama: frekans desc, sonra alfabetik
    return sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:top]


def classify(text: str) -> dict[str, Any]:
    low = (text or "").lower()
    scores = {dt: sum(low.count(h) for h in hints) for dt, hints in _CLASS_HINTS.items()}
    best = max(scores.items(), key=lambda kv: kv[1])
    doc_type = best[0] if best[1] > 0 else DocType.OTHER
    return {"doc_type": doc_type, "scores": scores}


def summarize(text: str, *, max_sentences: int = 3) -> str:
    """Extractive özet: cümleleri terim-frekansıyla skorla, en yüksek N'i ORİJİNAL SIRADA döndür."""
    sentences = _sentences(text)
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    freq: dict[str, int] = {}
    for w in _tokens(text):
        if len(w) > 2 and w not in _STOP:
            freq[w] = freq.get(w, 0) + 1
    scored = []
    for idx, s in enumerate(sentences):
        toks = [w for w in _tokens(s) if w in freq]
        score = sum(freq[w] for w in toks) / (len(toks) or 1)
        scored.append((idx, score))
    top_idx = sorted(sorted(scored, key=lambda t: t[0]),      # kararlılık: eşit skorda erken cümle
                     key=lambda t: t[1], reverse=True)[:max_sentences]
    keep = sorted(i for i, _ in top_idx)
    return " ".join(sentences[i] for i in keep)


def analyze(text: str, *, top_terms: int = 8, words_per_minute: int = 200) -> dict[str, Any]:
    """Deterministik yapısal analiz."""
    text = text or ""
    lines = text.splitlines()
    words = _tokens(text)
    sentences = _sentences(text)
    # bölüm sezgisi: kısa + iki-nokta/başlık-benzeri satırlar
    sections = [ln.strip() for ln in lines
                if ln.strip() and len(ln.strip()) <= 60 and (ln.strip().endswith(":")
                                                             or ln.strip().isupper()
                                                             or ln.strip().startswith("#"))]
    return {
        "chars": len(text), "lines": len(lines), "words": len(words), "sentences": len(sentences),
        "reading_time_min": round(len(words) / max(1, words_per_minute), 2),
        "top_terms": [{"term": t, "count": c} for t, c in term_frequencies(text, top=top_terms)],
        "sections": sections[:20],
    }


__all__ = ["analyze", "classify", "summarize", "term_frequencies"]
