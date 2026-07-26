"""MIO Core · Customer Success Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Account + support ticket + CSAT + deterministik health score + churn-risk. Health = 100 - açık ticket
ağırlığı + (avg_csat - 3)*10, [0,100] kırpılır. Churn-risk = health < eşik. authz · validation · events · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, CSEvents, customer_contract
from .models import (
    Account,
    CSConfig,
    Feedback,
    NotFoundError,
    Priority,
    Ticket,
    TicketStatus,
    UnauthorizedError,
    ValidationError,
)
from .repository import CustomerRepository

logger = logging.getLogger("mio.domain.customer_success")


class CustomerSuccessDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: CustomerRepository, *, bus=None,
                 config: Optional[CSConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or CSConfig()
        self._metrics = {"accounts": 0, "tickets": 0, "resolved": 0, "feedback": 0, "churn_flags": 0}

    # ------------------------------------------------------------------ #
    def add_account(self, actor: str, name: str, *, tier: str = "standard") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "hesap adı")
        a = Account(name=name, tier=tier)
        self._repo.put_account(a)
        self._metrics["accounts"] += 1
        self._emit(CSEvents.ACCOUNT_ADDED, {"actor": actor, "id": a.id})
        return a.to_dict()

    def open_ticket(self, actor: str, account_id: str, subject: str, *,
                    priority: str = Priority.MEDIUM) -> dict[str, Any]:
        self._authorize_writer(actor)
        self._require_account(account_id)
        subject = self._require(subject, "konu")
        if priority not in Priority.ALL:
            raise ValidationError(f"Geçersiz öncelik: {priority}")
        t = Ticket(account_id=account_id, subject=subject, priority=priority)
        self._repo.put_ticket(t)
        self._metrics["tickets"] += 1
        self._emit(CSEvents.TICKET_OPENED, {"account_id": account_id, "id": t.id, "priority": priority})
        return t.to_dict()

    def update_ticket(self, actor: str, ticket_id: str, status: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        if status not in TicketStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        t = self._repo.get_ticket(ticket_id)
        if t is None:
            raise NotFoundError(f"Ticket bulunamadı: {ticket_id}")
        t.status = status
        self._repo.put_ticket(t)
        if status == TicketStatus.RESOLVED:
            self._metrics["resolved"] += 1
            self._emit(CSEvents.TICKET_RESOLVED, {"id": ticket_id})
        return t.to_dict()

    def record_feedback(self, actor: str, account_id: str, score: int, *,
                        comment: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        self._require_account(account_id)
        if not (1 <= int(score) <= 5):
            raise ValidationError("CSAT 1-5 aralığında olmalı")
        f = Feedback(account_id=account_id, score=int(score), comment=comment)
        self._repo.put_feedback(f)
        self._metrics["feedback"] += 1
        self._emit(CSEvents.FEEDBACK_RECORDED, {"account_id": account_id, "score": int(score)})
        return f.to_dict()

    # -- deterministik health + churn ------------------------------------ #
    def health(self, actor: str, account_id: str) -> dict[str, Any]:
        self._authorize(actor)
        self._require_account(account_id)
        tickets = self._repo.tickets_for(account_id)
        feedback = self._repo.feedback_for(account_id)
        penalty = sum(Priority.WEIGHT.get(t.priority, 0) for t in tickets
                      if t.status in TicketStatus.ACTIVE)
        avg_csat = round(sum(f.score for f in feedback) / len(feedback), 2) if feedback else None
        csat_adj = (avg_csat - 3) * 10 if avg_csat is not None else 0
        score = max(0.0, min(100.0, round(100 - penalty + csat_adj, 1)))
        churn = score < self._cfg.churn_risk_below
        if churn:
            self._metrics["churn_flags"] += 1
            self._emit(CSEvents.CHURN_RISK, {"account_id": account_id, "health": score})
        return {"account_id": account_id, "health_score": score, "churn_risk": churn,
                "open_tickets": sum(1 for t in tickets if t.status in TicketStatus.ACTIVE),
                "avg_csat": avg_csat, "note": "CSAT yok → nötr kabul edilir" if avg_csat is None else ""}

    def list_accounts(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [a.to_dict() for a in self._repo.all_accounts()]

    def list_tickets(self, actor: str, account_id: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        self._require_account(account_id)
        return [t.to_dict() for t in self._repo.tickets_for(account_id)]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"accounts": self._repo.account_count(), "tickets": self._repo.ticket_count(),
                "open_tickets": self._repo.ticket_count(status=TicketStatus.OPEN),
                "feedback": self._repo.feedback_count(),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return customer_contract()

    # ------------------------------------------------------------------ #
    def _require_account(self, account_id: str) -> Account:
        a = self._repo.get_account(account_id)
        if a is None:
            raise NotFoundError(f"Hesap bulunamadı: {account_id}")
        return a

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' müşteri-başarısı erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' müşteri-başarısı yazımı için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
