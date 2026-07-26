"""MIO Core · Autonomous Operations Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

**Anayasa (EN HASSAS): otonom aksiyon KARAR VERMEZ; Executive'e ÖNERİ üretir; uygulama Madde 24 onayıyla.**
Operasyon kuralı registry + **deterministik tetik/koşul değerlendirme** + öneri üretimi + aksiyon durum makinesi.
Kapalı-döngü otomasyon YALNIZ açıkça allowlisted güvenli aksiyonlarda + closed_loop açıkken (opt-in; varsayılan
kapalı). Aksiyon yürütme enjekte edilen action adapter'a (DI) delege; yoksa **no_connector** (uydurma sonuç YOK —
Madde 8). İnsan/Executive gözetimi zorunlu. Gerçek yürütme çekirdekte YOK. authz · validation · events ·
observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, AutoOpsEvents, auto_ops_contract
from .models import (
    AutoOpsConfig,
    COMPARATORS,
    NotFoundError,
    OpsRule,
    Proposal,
    ProposalStatus,
    Severity,
    UnauthorizedError,
    ValidationError,
)
from .repository import AutoOpsRepository

logger = logging.getLogger("mio.domain.autonomous_ops")

Action = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AutonomousOperationsDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: AutoOpsRepository, *, bus=None,
                 config: Optional[AutoOpsConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or AutoOpsConfig()
        self._actions: dict[str, tuple[Action, str]] = {}   # action adı -> (fn, adapter adı)
        self._metrics = {"rules": 0, "observations": 0, "proposals": 0, "auto_executed": 0,
                         "approved": 0, "rejected": 0, "no_connector": 0, "failed": 0}

    # ------------------------------------------------------------------ #
    def register_action(self, action: str, fn: Action, *, name: str = "adapter") -> None:
        """Bir aksiyon için GERÇEK yürütme connector'ı bağlar (kompozisyon-zamanı DI)."""
        action = self._require(action, "aksiyon")
        self._actions[action] = (fn, name)

    def add_rule(self, actor: str, name: str, metric: str, comparator: str, threshold: float,
                 action: str, *, severity: str = Severity.WARNING, enabled: bool = True) -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "kural adı")
        metric = self._require(metric, "metrik")
        action = self._require(action, "aksiyon")
        if comparator not in COMPARATORS:
            raise ValidationError(f"Geçersiz karşılaştırıcı: {comparator}")
        if severity not in Severity.ALL:
            raise ValidationError(f"Geçersiz önem: {severity}")
        try:
            thr = float(threshold)
        except (TypeError, ValueError):
            raise ValidationError(f"Sayısal eşik bekleniyor: {threshold!r}")
        rule = OpsRule(name=name, metric=metric, comparator=comparator, threshold=thr, action=action,
                       severity=severity, enabled=enabled)
        self._repo.put_rule(rule)
        self._metrics["rules"] += 1
        self._emit(AutoOpsEvents.RULE_ADDED, {"id": rule.id, "metric": metric, "action": action})
        return rule.to_dict()

    def observe(self, actor: str, metric: str, value: float) -> list[dict[str, Any]]:
        """Metrik gözlemi → deterministik kuralları değerlendir. Tetikleneni ÖNERİYE dönüştür (Madde 24)."""
        self._authorize_writer(actor)
        metric = self._require(metric, "metrik")
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"Sayısal değer bekleniyor: {value!r}")
        self._metrics["observations"] += 1
        out: list[dict[str, Any]] = []
        for rule in self._repo.rules_for(metric):
            if not COMPARATORS[rule.comparator](val, rule.threshold):
                continue
            proposal = Proposal(rule_id=rule.id, action=rule.action, metric=metric, value=val,
                                severity=rule.severity, status=ProposalStatus.REQUIRES_APPROVAL)
            self._metrics["proposals"] += 1
            self._emit(AutoOpsEvents.PROPOSAL_CREATED, {"id": proposal.id, "action": rule.action,
                       "severity": rule.severity})
            # Kapalı-döngü YALNIZ allowlisted güvenli aksiyon + closed_loop açıkken (aksi: öneri kalır)
            if self._cfg.may_auto_execute(rule.action):
                proposal.auto = True
                self._emit(AutoOpsEvents.AUTO_EXECUTED, {"id": proposal.id, "action": rule.action})
                self._dispatch(proposal)          # dürüst: adapter yoksa no_connector
                self._metrics["auto_executed"] += 1
            else:
                self._repo.put_proposal(proposal)   # Executive'e öneri; onaysız YÜRÜTÜLMEZ
            out.append(proposal.to_dict())
        return out

    def approve_proposal(self, actor: str, proposal_id: str) -> dict[str, Any]:
        """Öneriyi onaylar ve uygular (yalnız approver — Madde 24)."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' öneri uygulayamaz (Madde 24)")
        p = self._require_proposal(proposal_id)
        if p.status != ProposalStatus.REQUIRES_APPROVAL:
            raise ValidationError(f"Yalnız 'requires_approval' onaylanır (durum: {p.status})")
        p.approved_by = actor
        self._emit(AutoOpsEvents.APPROVED, {"id": proposal_id, "by": actor})
        self._metrics["approved"] += 1
        return self._dispatch(p)

    def reject_proposal(self, actor: str, proposal_id: str, *, reason: str = "") -> dict[str, Any]:
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' öneri reddedemez (Madde 24)")
        p = self._require_proposal(proposal_id)
        if p.status != ProposalStatus.REQUIRES_APPROVAL:
            raise ValidationError(f"Yalnız 'requires_approval' reddedilir (durum: {p.status})")
        p.status = ProposalStatus.REJECTED
        p.rejected_reason = (reason or "manual_reject").strip()
        p.finished_at = _now()
        self._repo.put_proposal(p)
        self._metrics["rejected"] += 1
        self._emit(AutoOpsEvents.REJECTED, {"id": proposal_id, "reason": p.rejected_reason})
        return p.to_dict()

    def _dispatch(self, p: Proposal) -> dict[str, Any]:
        entry = self._actions.get(p.action)
        if entry is None:                       # DÜRÜST: gerçek aksiyon adapter'ı bağlı değil
            p.status = ProposalStatus.NO_CONNECTOR
            p.finished_at = _now()
            self._repo.put_proposal(p)
            self._metrics["no_connector"] += 1
            self._emit(AutoOpsEvents.NO_CONNECTOR, {"id": p.id, "action": p.action})
            return p.to_dict()
        fn, name = entry
        p.connector = name
        try:
            result = fn({"action": p.action, "metric": p.metric, "value": p.value,
                         "proposal": p.to_dict()})
            p.status = ProposalStatus.EXECUTED
            p.result = dict(result or {})
            self._emit(AutoOpsEvents.EXECUTED, {"id": p.id, "action": p.action, "auto": p.auto})
        except Exception as exc:  # noqa: BLE001 — aksiyon hatası öneriye dönüşür, sistemi bozmaz
            p.status = ProposalStatus.FAILED
            p.error = str(exc)[:300]
            self._metrics["failed"] += 1
            self._emit(AutoOpsEvents.FAILED, {"id": p.id, "error": p.error})
        p.finished_at = _now()
        self._repo.put_proposal(p)
        return p.to_dict()

    # -- sorgular -------------------------------------------------------- #
    def get_proposal(self, actor: str, proposal_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_proposal(proposal_id).to_dict()

    def list_proposals(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in ProposalStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [p.to_dict() for p in self._repo.all_proposals(status=status)]

    def list_rules(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [r.to_dict() for r in self._repo.all_rules()]

    def actions(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"registered": sorted(self._actions), "safe_allowlist": sorted(self._cfg.safe_actions),
                "closed_loop_enabled": self._cfg.closed_loop_enabled}

    def stats(self) -> dict[str, Any]:
        return {"rules": self._repo.rule_count(), "proposals": self._repo.proposal_count(),
                "pending_approval": self._repo.proposal_count(status=ProposalStatus.REQUIRES_APPROVAL),
                "actions": len(self._actions), "closed_loop_enabled": self._cfg.closed_loop_enabled,
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return auto_ops_contract()

    # ------------------------------------------------------------------ #
    def _require_proposal(self, proposal_id: str) -> Proposal:
        p = self._repo.get_proposal(proposal_id)
        if p is None:
            raise NotFoundError(f"Öneri bulunamadı: {proposal_id}")
        return p

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' otonom operasyon erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' kural/gözlem için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
