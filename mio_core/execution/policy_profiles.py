"""MIO Core · Policy Profiles (Öncelik 10) — mod-tabanlı güvenlik profilleri, LLM-BAĞIMSIZ, deterministik.

Tek tek kural yerine profil: Safe / Developer / Business / Autonomous / ReadOnly / Offline / HighSecurity.
Aktif profil bir yeteneğe izin/onay kararını modüle eder. Çekirdek dokunulmaz — Executive/orchestrator
bir kapı olarak `evaluate(cap)` çağırır."""

from __future__ import annotations

from dataclasses import dataclass, field

from mio_core.capability import Capability, RiskLevel
from mio_core.events import Ev

__all__ = ["PolicyProfile", "PolicyProfiles"]

_NETWORK_CATEGORIES = {"web_search", "messaging", "payment", "database"}


@dataclass
class PolicyProfile:
    name: str
    description: str = ""
    read_only: bool = False                      # yazma/yüksek-risk bloklu
    offline: bool = False                        # ağ gerektiren kategoriler bloklu
    autonomous: bool = False                     # onayları gevşetir (sabit blokları değil)
    block_categories: set = field(default_factory=set)
    block_risk: set = field(default_factory=set)  # bloklu risk seviyeleri
    require_user_categories: set = field(default_factory=set)


class PolicyProfiles:
    def __init__(self, *, bus=None) -> None:
        self._profiles: dict[str, PolicyProfile] = {p.name: p for p in _defaults()}
        self._active = "safe"
        self._bus = bus

    def add(self, p: PolicyProfile) -> None:
        self._profiles[p.name] = p

    def activate(self, name: str) -> PolicyProfile:
        if name not in self._profiles:
            raise ValueError(f"Bilinmeyen profil: {name}")
        self._active = name
        if self._bus:
            self._bus.publish(Ev.POLICY_PROFILE, {"active": name})
        return self._profiles[name]

    @property
    def active(self) -> PolicyProfile:
        return self._profiles[self._active]

    def names(self) -> list[str]:
        return sorted(self._profiles)

    def evaluate(self, cap: Capability) -> tuple[bool, bool, str]:
        """(allowed, needs_user, reason) — aktif profile göre."""
        p = self.active
        destructive = cap.risk_level == RiskLevel.HIGH or cap.category == "payment"
        if p.read_only and destructive:
            return False, False, f"[{p.name}] salt-okunur: yazma/yüksek-risk bloklu"
        if p.offline and cap.category in _NETWORK_CATEGORIES:
            return False, False, f"[{p.name}] çevrimdışı: ağ kategorisi bloklu ({cap.category})"
        if cap.category in p.block_categories:
            return False, False, f"[{p.name}] kategori bloklu: {cap.category}"
        if cap.risk_level in p.block_risk:
            return False, False, f"[{p.name}] risk bloklu: {cap.risk_level}"
        needs_user = (cap.category in p.require_user_categories) or (destructive and not p.autonomous)
        if cap.incurs_cost and not p.autonomous:
            needs_user = True
        return True, needs_user, f"[{p.name}] izinli"


def _defaults() -> list[PolicyProfile]:
    return [
        PolicyProfile("safe", "Varsayılan güvenli", require_user_categories={"payment"}),
        PolicyProfile("developer", "Geliştirme — araçlar açık", autonomous=False),
        PolicyProfile("business", "İş — finansal onay sıkı", require_user_categories={"payment", "messaging"}),
        PolicyProfile("autonomous", "Otonom — onaylar gevşek (sabit bloklar korunur)", autonomous=True),
        PolicyProfile("read_only", "Salt-okunur", read_only=True),
        PolicyProfile("offline", "Çevrimdışı — ağ yok", offline=True),
        PolicyProfile("high_security", "Yüksek güvenlik", block_risk={RiskLevel.HIGH},
                      require_user_categories={"payment", "messaging", "database"}),
    ]
