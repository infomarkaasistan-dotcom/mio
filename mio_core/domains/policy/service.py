"""MIO Core · Policy Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Deterministik Policy Decision Point (PDP). `evaluate(action, context_tags)` → tek verdict (allow/deny/
require_approval). Çözüm: DENY > REQUIRE_APPROVAL > ALLOW; eşitlikte yüksek priority. Anayasal innate
politikalarla doğar (değiştirilemez). authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, PolicyEvents, policy_contract
from .models import (
    ImmutablePolicyError,
    NotFoundError,
    Policy,
    PolicyConfig,
    PolicyEffect,
    UnauthorizedError,
    ValidationError,
    default_innate_policies,
)
from .repository import PolicyRepository

logger = logging.getLogger("mio.domain.policy")


class PolicyDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: PolicyRepository, *, bus=None,
                 config: Optional[PolicyConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or PolicyConfig()
        self._metrics = {"evaluations": 0, "gated": 0, "defined": 0, "removed": 0}
        if self._repo.count() == 0:                     # doğuşta anayasal politikalarla gel
            for p in default_innate_policies():
                self._repo.put(p)

    # ------------------------------------------------------------------ #
    def evaluate(self, actor: str, action: str, *, context_tags: Optional[list] = None,
                 user_approved: bool = False) -> dict[str, Any]:
        """Deterministik PDP: eşleşen politikaları çözüp tek verdict üretir."""
        self._authorize(actor)
        action = self._require(action, "aksiyon")
        tags = set(context_tags or [])
        matched = [p for p in self._repo.all() if p.matches(action, tags)]
        if not matched:
            verdict, default_used = self._cfg.default_effect, True
        else:
            best = max(matched, key=lambda p: (PolicyEffect.PRECEDENCE[p.effect], p.priority))
            verdict, default_used = best.effect, False
        allow = self._resolve_allow(verdict, user_approved)
        self._metrics["evaluations"] += 1
        self._emit(PolicyEvents.EVALUATED, {"actor": actor, "action": action, "verdict": verdict})
        if verdict != PolicyEffect.ALLOW:
            self._metrics["gated"] += 1
            self._emit(PolicyEvents.GATED, {"action": action, "verdict": verdict})
        return {"action": action, "verdict": verdict, "allow": allow, "default_used": default_used,
                "user_approved": user_approved,
                "matched": [{"name": p.name, "effect": p.effect, "priority": p.priority,
                             "source": p.source} for p in
                            sorted(matched, key=lambda p: (PolicyEffect.PRECEDENCE[p.effect], p.priority),
                                   reverse=True)]}

    @staticmethod
    def _resolve_allow(verdict: str, user_approved: bool) -> bool:
        if verdict == PolicyEffect.DENY:
            return False
        if verdict == PolicyEffect.REQUIRE_APPROVAL:
            return bool(user_approved)             # yalnız onayla geçer
        return True

    # ------------------------------------------------------------------ #
    def define_policy(self, actor: str, name: str, effect: str, *, conditions: Optional[list] = None,
                      scope: str = "*", priority: int = 50, description: str = "") -> dict[str, Any]:
        self._authorize_admin(actor)
        name = self._require(name, "politika adı")
        if effect not in PolicyEffect.ALL:
            raise ValidationError(f"Geçersiz efekt: {effect}")
        if self._repo.get_by_name(name) is not None:
            raise ValidationError(f"Politika adı zaten var: {name}")
        policy = Policy(name=name, effect=effect, conditions=list(conditions or []), scope=scope or "*",
                        priority=int(priority), source="custom", description=description)
        self._repo.put(policy)
        self._metrics["defined"] += 1
        self._emit(PolicyEvents.DEFINED, {"actor": actor, "id": policy.id, "name": name, "effect": effect})
        return policy.to_dict()

    def remove_policy(self, actor: str, policy_id: str) -> None:
        self._authorize_admin(actor)
        policy = self._innate_guard(policy_id, "silinemez")
        self._repo.delete(policy.id)
        self._metrics["removed"] += 1
        self._emit(PolicyEvents.REMOVED, {"actor": actor, "id": policy_id})

    def set_enabled(self, actor: str, policy_id: str, enabled: bool) -> dict[str, Any]:
        self._authorize_admin(actor)
        if not enabled:
            policy = self._innate_guard(policy_id, "devre dışı bırakılamaz")   # innate kapatılamaz
        else:
            policy = self._require_policy(policy_id)
        policy.enabled = bool(enabled)
        self._repo.put(policy)
        self._emit(PolicyEvents.TOGGLED, {"actor": actor, "id": policy_id, "enabled": policy.enabled})
        return policy.to_dict()

    def list_policies(self, actor: str, *, scope: Optional[str] = None,
                      effect: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if effect is not None and effect not in PolicyEffect.ALL:
            raise ValidationError(f"Geçersiz efekt: {effect}")
        out = self._repo.all()
        if scope is not None:
            out = [p for p in out if p.scope == scope]
        if effect is not None:
            out = [p for p in out if p.effect == effect]
        return [p.to_dict() for p in out]

    def get_policy(self, actor: str, policy_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_policy(policy_id).to_dict()

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        policies = self._repo.all()
        by_effect = {e: 0 for e in PolicyEffect.ALL}
        innate = enabled = 0
        for p in policies:
            by_effect[p.effect] = by_effect.get(p.effect, 0) + 1
            innate += 1 if p.source == "innate" else 0
            enabled += 1 if p.enabled else 0
        return {"total": len(policies), "innate": innate, "custom": len(policies) - innate,
                "enabled": enabled, "by_effect": by_effect, **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return policy_contract()

    # ------------------------------------------------------------------ #
    def _innate_guard(self, policy_id: str, verb: str) -> Policy:
        policy = self._require_policy(policy_id)
        if policy.source == "innate":
            raise ImmutablePolicyError(f"Innate (anayasal) politika {verb}: {policy.name}")
        return policy

    def _require_policy(self, policy_id: str) -> Policy:
        policy = self._repo.get(policy_id)
        if policy is None:
            raise NotFoundError(f"Politika bulunamadı: {policy_id}")
        return policy

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' politika erişimi için yetkili değil")

    def _authorize_admin(self, actor: str) -> None:
        if not self._cfg.is_admin(actor):
            raise UnauthorizedError(f"'{actor}' politika yönetimi için yetkili değil (admin gerekir)")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
