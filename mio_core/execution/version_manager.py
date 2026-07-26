"""MIO Core · MCP Version Manager (Öncelik 3) — sürüm takibi + öneri, LLM-BAĞIMSIZ, deterministik.

Her MCP için current/latest/compatibility/breaking/migration/deprecated izlenir. Executive'e öneri:
update | suggest | hold | block. 'latest' bir dış kaynaktan (registry/npm) enjekte edilir; yoksa dürüstçe
'bilinmiyor' (uydurma sürüm yok)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from mio_core.events import Ev

__all__ = ["VersionInfo", "VersionManager"]


@dataclass
class VersionInfo:
    name: str
    current: str = ""
    latest: Optional[str] = None
    breaking_changes: bool = False
    deprecated: bool = False
    migration_notes: str = ""
    required_runtime: str = ""
    required_permissions: list[str] = field(default_factory=list)

    def outdated(self) -> bool:
        return bool(self.latest) and self.latest != self.current

    def to_dict(self):
        return {"name": self.name, "current": self.current, "latest": self.latest,
                "outdated": self.outdated(), "breaking_changes": self.breaking_changes,
                "deprecated": self.deprecated, "migration_notes": self.migration_notes}


class VersionManager:
    def __init__(self, *, bus=None) -> None:
        self._versions: dict[str, VersionInfo] = {}
        self._bus = bus

    def register(self, name: str, current: str = "", **kw) -> VersionInfo:
        vi = VersionInfo(name=name, current=current, **kw)
        self._versions[name] = vi
        return vi

    def set_latest(self, name: str, latest: str, *, breaking: bool = False,
                   deprecated: bool = False, migration_notes: str = "") -> VersionInfo:
        vi = self._versions.setdefault(name, VersionInfo(name=name))
        vi.latest, vi.breaking_changes, vi.deprecated, vi.migration_notes = \
            latest, breaking, deprecated, migration_notes
        if self._bus and vi.outdated():
            self._bus.publish(Ev.VERSION_UPDATE, vi.to_dict())
        return vi

    def get(self, name: str) -> Optional[VersionInfo]:
        return self._versions.get(name)

    def recommendation(self, name: str) -> str:
        """Executive kararı: update | suggest | hold | block | up_to_date | unknown."""
        vi = self._versions.get(name)
        if vi is None:
            return "unknown"
        if vi.deprecated:
            return "block"                       # kullanımdan kaldırılmış → engelle
        if not vi.latest:
            return "unknown"
        if not vi.outdated():
            return "up_to_date"
        return "suggest" if vi.breaking_changes else "update"   # breaking → öner (elle), değilse güncelle

    def outdated(self) -> list[VersionInfo]:
        return [v for v in self._versions.values() if v.outdated()]

    def report(self) -> list[dict]:
        return [{**v.to_dict(), "recommendation": self.recommendation(v.name)}
                for v in self._versions.values()]
