"""MIO Core · Research Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Soruşturma + bulgu toplama + DETERMİNİSTİK sentez: aynı ifadeyi bildiren DİSTİNCT kaynak sayısı = corroboration;
eşik üstü → doğrulanmış, tek-kaynak/doğrulanmamış açıkça işaretlenir. Kanıt uydurulmaz (yalnız girilen
bulgulardan). LLM prose-sentezi danışmandır; yapısal sentez çekirdektedir. authz · validation · events · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, ResearchEvents, research_contract
from .models import (
    Credibility,
    Finding,
    Inquiry,
    InquiryStatus,
    NotFoundError,
    ResearchConfig,
    UnauthorizedError,
    ValidationError,
)
from .repository import ResearchRepository

logger = logging.getLogger("mio.domain.research")


class ResearchDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: ResearchRepository, *, bus=None,
                 config: Optional[ResearchConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or ResearchConfig()
        self._metrics = {"inquiries": 0, "findings": 0, "verified": 0, "syntheses": 0}

    # ------------------------------------------------------------------ #
    def start_inquiry(self, actor: str, question: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        q = Inquiry(question=self._require(question, "araştırma sorusu"))
        self._repo.put_inquiry(q)
        self._metrics["inquiries"] += 1
        self._emit(ResearchEvents.INQUIRY_STARTED, {"actor": actor, "id": q.id})
        return q.to_dict()

    def add_finding(self, actor: str, inquiry_id: str, statement: str, *, source: str = "",
                    credibility: str = Credibility.MEDIUM) -> dict[str, Any]:
        self._authorize_writer(actor)
        self._require_inquiry(inquiry_id)
        statement = self._require(statement, "bulgu ifadesi")
        if credibility not in Credibility.ALL:
            raise ValidationError(f"Geçersiz güvenilirlik: {credibility}")
        f = Finding(inquiry_id=inquiry_id, statement=statement, source=source.strip(),
                    credibility=credibility)
        self._repo.put_finding(f)
        self._metrics["findings"] += 1
        self._emit(ResearchEvents.FINDING_ADDED, {"inquiry_id": inquiry_id, "id": f.id,
                                                  "credibility": credibility})
        return f.to_dict()

    def verify_finding(self, actor: str, finding_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        f = self._repo.get_finding(finding_id)
        if f is None:
            raise NotFoundError(f"Bulgu bulunamadı: {finding_id}")
        f.verified = True
        self._repo.put_finding(f)
        self._metrics["verified"] += 1
        self._emit(ResearchEvents.FINDING_VERIFIED, {"id": finding_id})
        return f.to_dict()

    def synthesize(self, actor: str, inquiry_id: str) -> dict[str, Any]:
        """Deterministik sentez — soruşturmayı 'synthesized' işaretler."""
        self._authorize(actor)
        inq = self._require_inquiry(inquiry_id)
        report = self._build_synthesis(inq)
        inq.status = InquiryStatus.SYNTHESIZED
        self._repo.put_inquiry(inq)
        self._metrics["syntheses"] += 1
        self._emit(ResearchEvents.SYNTHESIZED, {"inquiry_id": inquiry_id,
                                                "corroborated": len(report["corroborated"])})
        return report

    def report(self, actor: str, inquiry_id: str) -> dict[str, Any]:
        """Salt-okunur sentez raporu (durum değiştirmez)."""
        self._authorize(actor)
        return self._build_synthesis(self._require_inquiry(inquiry_id))

    def list_inquiries(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in InquiryStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [q.to_dict() for q in self._repo.all_inquiries(status=status)]

    # ------------------------------------------------------------------ #
    def _build_synthesis(self, inq: Inquiry) -> dict[str, Any]:
        findings = self._repo.findings_for(inq.id)
        groups: dict[str, dict[str, Any]] = {}
        for f in findings:
            key = f.statement.strip().lower()
            g = groups.setdefault(key, {"statement": f.statement, "sources": set(), "weights": [],
                                        "verified": False})
            if f.source:
                g["sources"].add(f.source)
            g["weights"].append(Credibility.WEIGHT.get(f.credibility, 0.6))
            g["verified"] = g["verified"] or f.verified

        corroborated, single_source = [], []
        for g in groups.values():
            n_sources = len(g["sources"]) or 1     # kaynaksız bulgu → 1 kabul
            avg_w = sum(g["weights"]) / len(g["weights"])
            confidence = round(min(1.0, avg_w + 0.15 * (n_sources - 1) + (0.1 if g["verified"] else 0)), 3)
            entry = {"statement": g["statement"], "distinct_sources": n_sources,
                     "confidence": confidence, "verified": g["verified"]}
            if n_sources >= self._cfg.corroboration_min or g["verified"]:
                corroborated.append(entry)
            if n_sources == 1 and not g["verified"]:
                single_source.append(entry)
        corroborated.sort(key=lambda e: e["confidence"], reverse=True)
        all_sources = {f.source for f in findings if f.source}
        return {"inquiry": inq.to_dict(), "findings": len(findings), "distinct_sources": len(all_sources),
                "verified_findings": sum(1 for f in findings if f.verified),
                "corroborated": corroborated, "single_source_unverified": single_source,
                "note": "Sentez yalnız girilen bulgulardan; tek-kaynak/doğrulanmamış işaretli (uydurma yok)."}

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"inquiries": self._repo.inquiry_count(), "findings": self._repo.finding_count(),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return research_contract()

    # ------------------------------------------------------------------ #
    def _require_inquiry(self, inquiry_id: str) -> Inquiry:
        q = self._repo.get_inquiry(inquiry_id)
        if q is None:
            raise NotFoundError(f"Soruşturma bulunamadı: {inquiry_id}")
        return q

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' araştırma erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' araştırma yazımı için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
