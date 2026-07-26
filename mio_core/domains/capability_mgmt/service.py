"""MIO Core · Capability Management Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Çekirdek `CapabilityRegistry`'yi SARAR (Madde 15/16 — çekirdek yeniden yazılmaz). Governance ekler: maturity
yaşam-döngüsü (§7 geçerli geçişler), sürümlü sözleşme, deterministik yetenek seçimi (maturity sırası +
priority) ve Capability Evolution denetimi (Madde 26, write-through + append-only log). authorization ·
validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contract import CONTRACT_VERSION, CapEvents, capability_mgmt_contract
from .models import (
    Capability,
    CapabilityConfig,
    CapabilityRegistry,
    MaturityLevel,
    NotFoundError,
    RiskLevel,
    UnauthorizedError,
    VALID_MATURITY_TRANSITIONS,
    ValidationError,
    infer_category,
)
from .repository import CapabilityRepository

logger = logging.getLogger("mio.domain.capability_mgmt")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CapabilityManagementDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, registry: CapabilityRegistry, repository: CapabilityRepository, *, bus=None,
                 config: Optional[CapabilityConfig] = None) -> None:
        self._reg = registry
        self._repo = repository
        self._bus = bus
        self._cfg = config or CapabilityConfig()
        self._metrics = {"registered": 0, "maturity_changes": 0, "selections": 0}

    # ------------------------------------------------------------------ #
    def restore(self, actor: str) -> dict[str, Any]:
        """Kalıcı maturity override'larını in-memory registry'ye geri uygular (boot'ta çağrılır)."""
        self._authorize_admin(actor)
        applied = 0
        for name, maturity, contract_version in self._repo.all_states():
            cap = self._reg.get(name)
            if cap is not None:
                cap.maturity = maturity
                cap.contract_version = contract_version
                applied += 1
        return {"applied": applied}

    def register(self, actor: str, name: str, description: str = "", *, category: Optional[str] = None,
                 maturity: str = MaturityLevel.EXPERIMENTAL, contract_version: str = "1.0.0",
                 risk_level: str = RiskLevel.LOW, usable_by_brains: Optional[list] = None,
                 requires_user_approval: bool = False, incurs_cost: bool = False,
                 priority: int = 50) -> dict[str, Any]:
        self._authorize_admin(actor)
        name = self._require(name, "yetenek adı")
        if maturity not in MaturityLevel.ORDER:
            raise ValidationError(f"Geçersiz maturity: {maturity}")
        if self._reg.get(name) is not None:
            raise ValidationError(f"Yetenek zaten kayıtlı: {name}")
        cap = Capability(name=name, description=description,
                         category=category or infer_category(name), maturity=maturity,
                         contract_version=contract_version, risk_level=risk_level,
                         usable_by_brains=list(usable_by_brains or ["*"]),
                         requires_user_approval=requires_user_approval, incurs_cost=incurs_cost,
                         priority=int(priority), source="managed")
        self._reg.register(cap)
        self._persist(cap, "registered", f"maturity={maturity}")
        self._metrics["registered"] += 1
        self._emit(CapEvents.REGISTERED, {"actor": actor, "name": name, "maturity": maturity})
        return cap.to_dict()

    def set_maturity(self, actor: str, name: str, maturity: str) -> dict[str, Any]:
        """Maturity yaşam-döngüsü geçişi (§7). Geçersiz geçiş reddedilir; retired terminaldir."""
        self._authorize_admin(actor)
        cap = self._require_cap(name)
        if maturity not in MaturityLevel.ORDER:
            raise ValidationError(f"Geçersiz maturity: {maturity}")
        if maturity == cap.maturity:
            return cap.to_dict()                        # no-op (idempotent)
        allowed = VALID_MATURITY_TRANSITIONS.get(cap.maturity, set())
        if maturity not in allowed:
            raise ValidationError(
                f"Geçersiz maturity geçişi: {cap.maturity} → {maturity} (izinli: {sorted(allowed)})")
        prev, cap.maturity = cap.maturity, maturity
        self._persist(cap, "maturity_changed", f"{prev}→{maturity}")
        self._metrics["maturity_changes"] += 1
        self._emit(CapEvents.MATURITY_CHANGED, {"name": name, "from": prev, "to": maturity})
        return cap.to_dict()

    def deprecate(self, actor: str, name: str) -> dict[str, Any]:
        return self.set_maturity(actor, name, MaturityLevel.DEPRECATED)

    def retire(self, actor: str, name: str) -> dict[str, Any]:
        return self.set_maturity(actor, name, MaturityLevel.RETIRED)

    def set_connected(self, actor: str, name: str, connected: bool) -> dict[str, Any]:
        """Keşif sonucunu kaydeder (bağlı/değil). Yürütülebilirliği belirler."""
        self._authorize_admin(actor)
        cap = self._require_cap(name)
        self._reg.set_connected(name, bool(connected))
        self._repo.append_lifecycle(name, "connected", str(bool(connected)), _now())
        self._emit(CapEvents.CONNECTED, {"name": name, "connected": bool(connected)})
        return cap.to_dict()

    # ------------------------------------------------------------------ #
    def describe(self, actor: str, name: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_cap(name).to_dict()

    def list_capabilities(self, actor: str, *, category: Optional[str] = None,
                          maturity: Optional[str] = None, connected: Optional[bool] = None,
                          brain: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        out = self._reg.list()
        if category is not None:
            out = [c for c in out if c.category == category]
        if maturity is not None:
            out = [c for c in out if c.maturity == maturity]
        if connected is not None:
            out = [c for c in out if c.connected == connected]
        if brain is not None:
            out = [c for c in out if c.usable_by(brain)]
        return [c.to_dict() for c in out]

    def usable(self, actor: str, name: str) -> bool:
        """Bu yetenek ŞU AN yürütmeye seçilebilir mi? (USABLE maturity + connected)."""
        self._authorize(actor)
        cap = self._reg.get(name)
        return bool(cap and cap.maturity in MaturityLevel.USABLE and cap.connected)

    def select_best(self, actor: str, category: str, *, brain: str = "Executive",
                    only_connected: bool = True) -> Optional[dict[str, Any]]:
        """Bir kategoride EN İYİ yeteneği deterministik seçer: (maturity sırası, priority)."""
        self._authorize(actor)
        cands = [c for c in self._reg.list()
                 if c.category == category and c.maturity in MaturityLevel.USABLE
                 and c.usable_by(brain) and (c.connected or not only_connected)]
        if not cands:
            return None
        best = max(cands, key=lambda c: (MaturityLevel.ORDER.get(c.maturity, 0), c.priority))
        self._metrics["selections"] += 1
        self._emit(CapEvents.SELECTED, {"category": category, "name": best.name, "maturity": best.maturity})
        return best.to_dict()

    def lifecycle_history(self, actor: str, *, name: Optional[str] = None,
                          limit: int = 100) -> list[dict[str, Any]]:
        self._authorize(actor)
        return self._repo.lifecycle_recent(min(int(limit), 500), name=name)

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        caps = self._reg.list()
        by_maturity = {m: 0 for m in MaturityLevel.ORDER}
        for c in caps:
            by_maturity[c.maturity] = by_maturity.get(c.maturity, 0) + 1
        return {"total": len(caps), "connected": sum(1 for c in caps if c.connected),
                "usable": sum(1 for c in caps if c.maturity in MaturityLevel.USABLE and c.connected),
                "by_maturity": by_maturity, "lifecycle_events": self._repo.lifecycle_count(),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return capability_mgmt_contract()

    # ------------------------------------------------------------------ #
    def _persist(self, cap: Capability, kind: str, detail: str) -> None:
        self._repo.put_state(cap.name, cap.maturity, cap.contract_version, _now())
        self._repo.append_lifecycle(cap.name, kind, detail, _now())

    def _require_cap(self, name: str) -> Capability:
        cap = self._reg.get(name)
        if cap is None:
            raise NotFoundError(f"Yetenek bulunamadı: {name}")
        return cap

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' yetenek erişimi için yetkili değil")

    def _authorize_admin(self, actor: str) -> None:
        if not self._cfg.is_admin(actor):
            raise UnauthorizedError(f"'{actor}' yetenek yönetimi için yetkili değil (admin gerekir)")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
