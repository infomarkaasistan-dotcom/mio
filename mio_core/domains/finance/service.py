"""MIO Core · Finance Operations Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Gelir/gider defteri + nakit akışı/runway + Financial Rule. **Finansal yükümlülük (commitment) onaysız
EXECUTED olamaz** (Anayasa Madde 4); onay owner/Executive'dedir. Hesaplar deterministik (yalnız defterden).
authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, FinanceEvents, finance_contract
from .models import (
    Commitment,
    CommitmentStatus,
    FinanceConfig,
    FinancialRuleError,
    NotFoundError,
    Transaction,
    TxnKind,
    UnauthorizedError,
    ValidationError,
)
from .repository import FinanceRepository

logger = logging.getLogger("mio.domain.finance")


class FinanceDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: FinanceRepository, *, bus=None,
                 config: Optional[FinanceConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or FinanceConfig()
        self._metrics = {"transactions": 0, "commitments": 0, "approved": 0, "rejected": 0}

    # ------------------------------------------------------------------ #
    def record_transaction(self, actor: str, kind: str, amount: float, *, category: str = "general",
                           currency: str = "TRY", description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        if kind not in TxnKind.ALL:
            raise ValidationError(f"Geçersiz tür: {kind} (income/expense)")
        amount = self._positive(amount, "tutar")
        t = Transaction(kind=kind, amount=amount, currency=currency,
                        category=(category or "general").strip(), description=description)
        self._repo.add_transaction(t)
        self._metrics["transactions"] += 1
        self._emit(FinanceEvents.TRANSACTION_RECORDED, {"actor": actor, "kind": kind, "amount": amount})
        return t.to_dict()

    # -- Financial Rule (Madde 4) ---------------------------------------- #
    def record_commitment(self, actor: str, description: str, amount: float, *,
                          currency: str = "TRY") -> dict[str, Any]:
        """Finansal yükümlülük TALEBİ — daima 'pending_approval' başlar (onaysız yürürlüğe girmez)."""
        self._authorize_writer(actor)
        description = self._require(description, "yükümlülük açıklaması")
        amount = self._positive(amount, "tutar")
        c = Commitment(description=description, amount=amount, currency=currency,
                       status=CommitmentStatus.PENDING)
        self._repo.put_commitment(c)
        self._metrics["commitments"] += 1
        self._emit(FinanceEvents.COMMITMENT_REQUESTED, {"actor": actor, "id": c.id, "amount": amount})
        return c.to_dict()

    def approve_commitment(self, actor: str, commitment_id: str) -> dict[str, Any]:
        """Yükümlülüğü onayla + gideri deftere işle (Financial Rule: yalnız approver)."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' finansal yükümlülük onaylayamaz (Financial Rule: Madde 4)")
        c = self._require_commitment(commitment_id)
        if c.status != CommitmentStatus.PENDING:
            raise FinancialRuleError(f"Yalnız 'pending_approval' onaylanır (durum: {c.status})")
        c.status = CommitmentStatus.EXECUTED
        c.approved_by = actor
        self._repo.put_commitment(c)
        # Onaylanan yükümlülük gerçek gidere dönüşür (deterministik defter etkisi)
        self._repo.add_transaction(Transaction(kind=TxnKind.EXPENSE, amount=c.amount, currency=c.currency,
                                               category="commitment", description=c.description))
        self._metrics["approved"] += 1
        self._emit(FinanceEvents.COMMITMENT_APPROVED, {"id": commitment_id, "by": actor})
        return c.to_dict()

    def reject_commitment(self, actor: str, commitment_id: str) -> dict[str, Any]:
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' finansal yükümlülük reddedemez (Madde 4)")
        c = self._require_commitment(commitment_id)
        if c.status != CommitmentStatus.PENDING:
            raise FinancialRuleError(f"Yalnız 'pending_approval' reddedilir (durum: {c.status})")
        c.status = CommitmentStatus.REJECTED
        c.approved_by = actor
        self._repo.put_commitment(c)
        self._metrics["rejected"] += 1
        self._emit(FinanceEvents.COMMITMENT_REJECTED, {"id": commitment_id, "by": actor})
        return c.to_dict()

    # -- deterministik analiz -------------------------------------------- #
    def cash_flow(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        income = round(self._repo.sum_by_kind(TxnKind.INCOME), 2)
        expense = round(self._repo.sum_by_kind(TxnKind.EXPENSE), 2)
        return {"income": income, "expense": expense, "net": round(income - expense, 2),
                "balance": round(income - expense, 2)}

    def category_breakdown(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        out: dict[str, dict[str, float]] = {}
        for t in self._repo.all_transactions():
            b = out.setdefault(t.category, {"income": 0.0, "expense": 0.0})
            b[t.kind] = round(b[t.kind] + t.amount, 2)
        return {"categories": out}

    def runway(self, actor: str, *, months: float = 1.0) -> dict[str, Any]:
        """Deterministik runway: bakiye / aylık ortalama gider. Gider yoksa 'sınırsız' (dürüst)."""
        self._authorize(actor)
        expense = self._repo.sum_by_kind(TxnKind.EXPENSE)
        balance = self._repo.sum_by_kind(TxnKind.INCOME) - expense
        burn = round(expense / max(0.01, months), 2)
        runway_months = round(balance / burn, 2) if burn > 0 else None
        return {"balance": round(balance, 2), "monthly_burn": burn,
                "runway_months": runway_months,
                "note": "burn=0 → runway hesaplanamaz (gider yok)" if burn <= 0 else ""}

    def list_transactions(self, actor: str, *, kind: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in TxnKind.ALL:
            raise ValidationError(f"Geçersiz tür: {kind}")
        return [t.to_dict() for t in self._repo.all_transactions(kind=kind)]

    def list_commitments(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in CommitmentStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [c.to_dict() for c in self._repo.list_commitments(status=status)]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"transactions": self._repo.transaction_count(),
                "commitments": self._repo.commitment_count(),
                "pending_commitments": self._repo.commitment_count(status=CommitmentStatus.PENDING),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return finance_contract()

    # ------------------------------------------------------------------ #
    def _require_commitment(self, commitment_id: str) -> Commitment:
        c = self._repo.get_commitment(commitment_id)
        if c is None:
            raise NotFoundError(f"Yükümlülük bulunamadı: {commitment_id}")
        return c

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' finans erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' finans yazımı için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    @staticmethod
    def _positive(amount: float, label: str) -> float:
        a = float(amount)
        if a <= 0:
            raise ValidationError(f"{label} pozitif olmalı")
        return round(a, 2)

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
