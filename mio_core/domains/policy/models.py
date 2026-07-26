"""MIO Core · Policy Domain — modeller, innate politikalar, config (production-grade), LLM-BAĞIMSIZ.

Politika = merkezî, sürümlü, SORGULANABİLİR bir kısıt (allow/deny/require_approval). Policy Domain bir
deterministik Policy Decision Point'tir (PDP): herhangi bir domain bir aksiyon+bağlam için `evaluate` çağırır,
tek deterministik verdict alır. Anayasa'yı yansıtan innate politikalarla doğar. E4 (karar verdict'i) ve
vertical guardrail'lerini TAMAMLAR — onların yerine geçmez."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


class PolicyEffect:
    ALLOW = "allow"
    DENY = "deny"                      # sert red (bypass edilemez)
    REQUIRE_APPROVAL = "require_approval"   # onayla bypass edilebilir
    ALL = {ALLOW, DENY, REQUIRE_APPROVAL}
    # Çözüm önceliği (yüksek kazanır): DENY > REQUIRE_APPROVAL > ALLOW
    PRECEDENCE = {DENY: 3, REQUIRE_APPROVAL: 2, ALLOW: 1}


class PolicyError(Exception):
    """Policy Domain temel hatası."""


class ValidationError(PolicyError):
    pass


class UnauthorizedError(PolicyError):
    pass


class NotFoundError(PolicyError):
    pass


class ImmutablePolicyError(PolicyError):
    """Innate (anayasal) politika değiştirilemez/silinemez."""


@dataclass
class Policy:
    name: str
    effect: str
    conditions: list[str] = field(default_factory=list)   # hepsi bağlamda varsa eşleşir (AND)
    scope: str = "*"                                       # aksiyon adı ya da "*" (tümü)
    priority: int = 50                                     # eşit efektte yüksek öncelik kazanır
    enabled: bool = True
    source: str = "custom"                                # innate | custom
    description: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])

    def matches(self, action: str, tags: set[str]) -> bool:
        return (self.enabled and (self.scope == "*" or self.scope == action)
                and all(c in tags for c in self.conditions))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "effect": self.effect,
                "conditions": list(self.conditions), "scope": self.scope, "priority": self.priority,
                "enabled": self.enabled, "source": self.source, "description": self.description}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Policy":
        return cls(name=d["name"], effect=d["effect"], conditions=list(d.get("conditions") or []),
                   scope=d.get("scope", "*"), priority=int(d.get("priority", 50)),
                   enabled=bool(d.get("enabled", True)), source=d.get("source", "custom"),
                   description=d.get("description", ""), id=d.get("id") or uuid4().hex[:12])


def default_innate_policies() -> list[Policy]:
    """Anayasa'yı yansıtan DOĞUŞTAN politikalar (source=innate; değiştirilemez)."""
    return [
        Policy(name="financial-commitment-approval", effect=PolicyEffect.REQUIRE_APPROVAL,
               conditions=["financial_commitment"], scope="*", priority=95, source="innate",
               description="Financial Rule: kullanıcı onayı olmadan finansal yükümlülük oluşturulamaz."),
        Policy(name="new-expense-approval", effect=PolicyEffect.REQUIRE_APPROVAL,
               conditions=["new_expense"], scope="*", priority=80, source="innate",
               description="Para harcamak çözüm değildir: yeni maliyet onay + ücretsiz alternatif ister."),
        Policy(name="irreversible-approval", effect=PolicyEffect.REQUIRE_APPROVAL,
               conditions=["irreversible_action"], scope="*", priority=90, source="innate",
               description="Geri-alınamaz/dış aksiyon: Executive onayı + geri-alınabilirlik değerlendirmesi."),
    ]


@dataclass
class PolicyConfig:
    default_effect: str = PolicyEffect.ALLOW      # hiçbir politika eşleşmezse (izinci varsayılan)
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Planning", "Operations", "Workflow", "Security",
        "Finance", "Engineering", "Communication"})
    admin_actors: set = field(default_factory=lambda: {"owner", "Executive", "Security"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_admin(self, actor: str) -> bool:
        return actor == "owner" or actor in self.admin_actors


__all__ = [
    "PolicyEffect", "Policy", "default_innate_policies", "PolicyConfig",
    "PolicyError", "ValidationError", "UnauthorizedError", "NotFoundError", "ImmutablePolicyError",
]
