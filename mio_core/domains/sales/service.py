"""MIO Core · Sales & CRM Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Contact + opportunity/pipeline + ağırlıklı pipeline metrikleri + lead qualification. Hesaplar deterministik;
qualification önerisi karar DEĞİL (Executive'e gider). authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, SalesEvents, sales_contract
from .models import (
    Contact,
    ContactKind,
    NotFoundError,
    Opportunity,
    SalesConfig,
    Stage,
    UnauthorizedError,
    ValidationError,
)
from .repository import SalesRepository

logger = logging.getLogger("mio.domain.sales")


class SalesCRMDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: SalesRepository, *, bus=None,
                 config: Optional[SalesConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or SalesConfig()
        self._metrics = {"contacts": 0, "opportunities": 0, "stage_changes": 0, "qualifications": 0}

    # ------------------------------------------------------------------ #
    def add_contact(self, actor: str, name: str, *, kind: str = ContactKind.LEAD, email: str = "",
                    company: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "isim")
        if kind not in ContactKind.ALL:
            raise ValidationError(f"Geçersiz tür: {kind} (lead/customer)")
        c = Contact(name=name, kind=kind, email=email, company=company)
        self._repo.put_contact(c)
        self._metrics["contacts"] += 1
        self._emit(SalesEvents.CONTACT_ADDED, {"actor": actor, "id": c.id, "kind": kind})
        return c.to_dict()

    def add_opportunity(self, actor: str, contact_id: str, title: str, value: float, *,
                        currency: str = "TRY", stage: str = Stage.LEAD) -> dict[str, Any]:
        self._authorize_writer(actor)
        if self._repo.get_contact(contact_id) is None:
            raise NotFoundError(f"Contact bulunamadı: {contact_id}")
        title = self._require(title, "fırsat başlığı")
        if float(value) < 0:
            raise ValidationError("value negatif olamaz")
        if stage not in Stage.ALL:
            raise ValidationError(f"Geçersiz stage: {stage}")
        o = Opportunity(contact_id=contact_id, title=title, value=round(float(value), 2),
                        currency=currency, stage=stage)
        self._repo.put_opportunity(o)
        self._metrics["opportunities"] += 1
        self._emit(SalesEvents.OPPORTUNITY_ADDED, {"actor": actor, "id": o.id, "value": o.value})
        return o.to_dict()

    def advance_stage(self, actor: str, opp_id: str, stage: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        if stage not in Stage.ALL:
            raise ValidationError(f"Geçersiz stage: {stage}")
        o = self._repo.get_opportunity(opp_id)
        if o is None:
            raise NotFoundError(f"Fırsat bulunamadı: {opp_id}")
        prev, o.stage = o.stage, stage
        from datetime import datetime, timezone
        o.updated_at = datetime.now(timezone.utc).isoformat()
        self._repo.put_opportunity(o)
        self._metrics["stage_changes"] += 1
        self._emit(SalesEvents.STAGE_CHANGED, {"id": opp_id, "from": prev, "to": stage})
        return o.to_dict()

    # -- deterministik pipeline metrikleri ------------------------------- #
    def pipeline(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        opps = self._repo.all_opportunities()
        by_stage = {s: 0 for s in Stage.ALL}
        total_value = weighted = 0.0
        won = lost = 0
        for o in opps:
            by_stage[o.stage] = by_stage.get(o.stage, 0) + 1
            if o.stage in Stage.OPEN:
                total_value += o.value
                weighted += o.value * Stage.PROBABILITY[o.stage]
            won += 1 if o.stage == Stage.WON else 0
            lost += 1 if o.stage == Stage.LOST else 0
        win_rate = round(won / (won + lost), 3) if (won + lost) > 0 else None
        return {"opportunities": len(opps), "by_stage": by_stage,
                "open_value": round(total_value, 2), "weighted_value": round(weighted, 2),
                "won": won, "lost": lost, "win_rate": win_rate}

    def qualify(self, actor: str, *, context_tags: Optional[list] = None) -> dict[str, Any]:
        """Deterministik lead qualification (soğuk-lead → değer-önce). Öneri; karar Executive'de."""
        self._authorize(actor)
        tags = set(context_tags or [])
        recs = []
        if "cold_lead" in tags:
            recs.append("Soğuk lead: doğrudan satış değil, önce DEĞER sun (değer-önce yaklaşım).")
        if "budget_confirmed" in tags:
            recs.append("Bütçe teyitli: proposal aşamasına ilerlet.")
        if not recs:
            recs.append("Belirgin qualification sinyali yok; standart keşif görüşmesi öner.")
        self._metrics["qualifications"] += 1
        self._emit(SalesEvents.QUALIFIED, {"context": sorted(tags)})
        return {"context": sorted(tags), "recommendations": recs, "decision_authority": "Executive"}

    def list_contacts(self, actor: str, *, kind: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in ContactKind.ALL:
            raise ValidationError(f"Geçersiz tür: {kind}")
        return [c.to_dict() for c in self._repo.all_contacts(kind=kind)]

    def list_opportunities(self, actor: str, *, stage: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if stage is not None and stage not in Stage.ALL:
            raise ValidationError(f"Geçersiz stage: {stage}")
        return [o.to_dict() for o in self._repo.all_opportunities(stage=stage)]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"contacts": self._repo.contact_count(), "opportunities": self._repo.opportunity_count(),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return sales_contract()

    # ------------------------------------------------------------------ #
    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' satış erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' satış yazımı için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
