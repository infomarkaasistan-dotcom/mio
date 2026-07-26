"""MIO Core · Self Awareness Layer (ADR-0002 Madde 3), LLM-BAĞIMSIZ.

Born Capable'ın en kritik parçası: MIO yalnız kimliği OLAN değil, kendini MODELLEYEN bir sistemdir. Sürekli
şu soruların cevabını bilir: Ben kimim? Misyonum/amacım ne? Hedeflerim? Hangi Brain'lerim/araçlarım var?
Hangi MCP'ler aktif? Hangi modeller/donanım? Yetki seviyem? Neleri yapabilirim/yapamam? Hangi kısıtlar?

Bu, tek bir doğruluk kaynağından (E1 State + Brain Registry + Capability Registry + kurulumda keşfedilen
bilgiler) TÜRETİLİR — uydurma yok. Keşfedilmemiş alanlar dürüstçe boş/None döner (Born Capable dürüstlüğü).
"""

from __future__ import annotations

from typing import Any, Optional

from .brains import BrainRegistry
from .capability import CapabilityRegistry
from .executive.state import ExecutiveState

__all__ = ["SelfAwareness"]


class SelfAwareness:
    """MIO'nun öz-modeli. E1 + Brain/Capability Registry + keşfedilen bilgileri birleştirir."""

    def __init__(self, state: ExecutiveState, brains: BrainRegistry, capabilities: CapabilityRegistry, *,
                 available_models: Optional[list[str]] = None,
                 hardware: Optional[dict[str, Any]] = None,
                 authority_level: str = "user_delegated") -> None:
        self._state = state
        self._brains = brains
        self._caps = capabilities
        self._models = list(available_models or [])          # kurulumda keşfedilen (layer 2)
        self._hardware = dict(hardware or {})                # kurulumda keşfedilen (layer 2)
        self._authority = authority_level

    def can_i(self, capability_name: str) -> tuple[bool, str]:
        """'Bunu yapabilir miyim?' — tanımlı VE bağlı mı, değilse neden."""
        cap = self._caps.get(capability_name)
        if cap is None:
            return False, f"'{capability_name}' yeteneğini tanımıyorum (kayıtlı değil)."
        if not cap.connected:
            alt = f" Alternatif: {', '.join(cap.alternatives)}." if cap.alternatives else ""
            return False, f"'{capability_name}' tanımlı ama bağlı değil (bu ortamda erişimim yok).{alt}"
        note = ""
        if cap.requires_user_approval:
            note = " (kullanıcı onayı gerekir)"
        return True, f"Evet — '{capability_name}' bağlı ve kullanılabilir{note}."

    def what_i_can_do(self) -> list[str]:
        """Bağlı yeteneklerin yapabildikleri (aggregate)."""
        out: list[str] = []
        for c in self._caps.list_connected():
            out.extend(c.can_do or [c.name])
        return sorted(set(out))

    def what_i_cannot_do(self) -> list[str]:
        """Bağlı-olmayan yetenekler + yeteneklerin açıkça yapamadıkları."""
        out: list[str] = []
        for c in self._caps.list_disconnected():
            out.append(f"{c.name} (bağlı değil)")
        for c in self._caps.list():
            out.extend(c.cannot_do)
        return sorted(set(out))

    def constraints(self) -> list[str]:
        """Hangi kısıtlar altındayım — Purpose kuralları + onay gerektiren yetenekler."""
        cons: list[str] = []
        purpose = self._state.get_purpose()
        if purpose:
            if purpose.financial_rule:
                cons.append("Finansal: " + purpose.financial_rule)
            for p in purpose.core_principles:
                cons.append("İlke: " + p)
        approval = [c.name for c in self._caps.list() if c.requires_user_approval]
        if approval:
            cons.append("Kullanıcı onayı gerektiren yetenekler: " + ", ".join(approval))
        return cons

    def self_model(self) -> dict[str, Any]:
        """Tam öz-model — ADR-0002 Madde 3'teki tüm soruların cevabı, tek doğruluk kaynağından türetilmiş."""
        identity = self._state.get_identity()
        mission = self._state.get_mission()
        purpose = self._state.get_purpose()
        active_mcps = [c.name for c in self._caps.list_connected() if c.source == "mcp"]
        return {
            "who_am_i": identity.to_dict() if identity else None,
            "mission": mission.to_dict() if mission else None,
            "purpose": purpose.to_dict() if purpose else None,
            "current_goals": [g.to_dict() for g in self._state.active_goals()],
            "brains": [b.name for b in self._brains.list()],
            "capabilities": {
                "connected": [c.name for c in self._caps.list_connected()],
                "disconnected": [c.name for c in self._caps.list_disconnected()],
            },
            "active_mcps": active_mcps,
            "available_models": list(self._models),        # boşsa: henüz keşfedilmedi (dürüst)
            "hardware": dict(self._hardware),               # boşsa: henüz keşfedilmedi (dürüst)
            "authority_level": self._authority,
            "what_i_can_do": self.what_i_can_do(),
            "what_i_cannot_do": self.what_i_cannot_do(),
            "constraints": self.constraints(),
        }

    # -- kurulum keşfi (layer 2) enjekte edilir --------------------------- #
    def set_discovered(self, *, available_models: Optional[list[str]] = None,
                       hardware: Optional[dict[str, Any]] = None,
                       authority_level: Optional[str] = None) -> None:
        if available_models is not None:
            self._models = list(available_models)
        if hardware is not None:
            self._hardware = dict(hardware)
        if authority_level is not None:
            self._authority = authority_level
