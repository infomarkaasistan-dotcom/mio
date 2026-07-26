"""MIO Core · Resource & Runtime Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Resource Awareness (Madde 30): probe'tan GERÇEK kaynak snapshot'ı (uydurma yok), API/Token/Cost bütçe takibi
ve deterministik darboğaz/yükseltme analizi. Executive `can_afford`/`bottlenecks` ile kaynak-farkında karar
verir. authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from mio_core.adapters.hardware import discover_hardware

from .contract import CONTRACT_VERSION, ResourceEvents, resources_contract
from .models import (
    Budget,
    NotFoundError,
    ResourceConfig,
    UnauthorizedError,
    ValidationError,
)
from .repository import ResourceRepository

logger = logging.getLogger("mio.domain.resources")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResourceRuntimeDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: ResourceRepository, *, probe: Optional[Callable[[], dict]] = None,
                 bus=None, config: Optional[ResourceConfig] = None) -> None:
        self._repo = repository
        self._probe = probe or discover_hardware      # GERÇEK kaynak sağlayıcı (enjekte edilebilir)
        self._bus = bus
        self._cfg = config or ResourceConfig()
        self._metrics = {"snapshots": 0, "consumptions": 0, "exceeds": 0}

    # ------------------------------------------------------------------ #
    def snapshot(self, actor: str) -> dict[str, Any]:
        """Anlık GERÇEK kaynak durumu (probe). Eksik alan dürüstçe atlanır."""
        self._authorize(actor)
        snap = dict(self._probe() or {})
        self._derive(snap)
        snap["at"] = _now()
        self._repo.append_snapshot(snap, snap["at"])
        self._repo.prune_snapshots(self._cfg.snapshot_history)
        self._metrics["snapshots"] += 1
        self._emit(ResourceEvents.SNAPSHOT, {"actor": actor})
        return snap

    def _derive(self, snap: dict) -> None:
        total, avail = snap.get("ram_total_gb"), snap.get("ram_available_gb")
        if isinstance(total, (int, float)) and total > 0 and isinstance(avail, (int, float)):
            snap["ram_free_ratio"] = round(avail / total, 4)
            snap["ram_used_pct"] = round((1 - avail / total) * 100, 1)

    # -- bütçe (Madde 30: API/Token/Cost) -------------------------------- #
    def set_budget(self, actor: str, name: str, limit: float, *, unit: str = "units") -> dict[str, Any]:
        self._authorize_admin(actor)
        name = self._require(name, "bütçe adı")
        if float(limit) < 0:
            raise ValidationError("limit negatif olamaz")
        existing = self._repo.get_budget(name)
        b = Budget(name=name, limit=float(limit), unit=unit,
                   consumed=existing.consumed if existing else 0.0)
        self._repo.put_budget(b)
        self._emit(ResourceEvents.BUDGET_SET, {"name": name, "limit": limit, "unit": unit})
        return b.to_dict()

    def consume(self, actor: str, name: str, amount: float) -> dict[str, Any]:
        self._authorize_writer(actor)
        if float(amount) < 0:
            raise ValidationError("tüketim negatif olamaz")
        b = self._require_budget(name)
        b.consumed = round(b.consumed + float(amount), 6)
        b.updated_at = _now()
        self._repo.put_budget(b)
        self._metrics["consumptions"] += 1
        self._emit(ResourceEvents.BUDGET_CONSUMED, {"name": name, "amount": amount,
                                                    "remaining": b.remaining})
        if not b.within:
            self._metrics["exceeds"] += 1
            self._emit(ResourceEvents.BUDGET_EXCEEDED, {"name": name, "consumed": b.consumed,
                                                        "limit": b.limit})
        return {**b.to_dict(), "over_budget": not b.within}

    def can_afford(self, actor: str, name: str, amount: float) -> dict[str, Any]:
        """Karar-öncesi deterministik kontrol: bu tüketim bütçeye sığar mı?"""
        self._authorize(actor)
        b = self._require_budget(name)
        affordable = (b.consumed + float(amount)) <= b.limit
        return {"name": name, "amount": amount, "affordable": affordable, "remaining": b.remaining}

    def reset_budget(self, actor: str, name: str) -> dict[str, Any]:
        self._authorize_admin(actor)
        b = self._require_budget(name)
        b.consumed = 0.0
        b.updated_at = _now()
        self._repo.put_budget(b)
        return b.to_dict()

    def budget_status(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [b.to_dict() for b in self._repo.all_budgets()]

    # -- darboğaz + öneri (deterministik) -------------------------------- #
    def bottlenecks(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        snap = self._repo.latest_snapshot() or self._current()
        out = []
        fr = snap.get("ram_free_ratio")
        if isinstance(fr, (int, float)) and fr < self._cfg.ram_bottleneck_free_ratio:
            out.append({"resource": "ram", "severity": "high",
                        "detail": f"boş RAM oranı %{round(fr * 100, 1)} (eşik %{self._cfg.ram_bottleneck_free_ratio * 100:.0f})"})
        cpu = snap.get("cpu_percent")
        if isinstance(cpu, (int, float)) and cpu > self._cfg.cpu_bottleneck_percent:
            out.append({"resource": "cpu", "severity": "high", "detail": f"CPU %{cpu}"})
        disk = snap.get("disk_free_gb")
        if isinstance(disk, (int, float)) and disk < self._cfg.disk_bottleneck_free_gb:
            out.append({"resource": "disk", "severity": "medium", "detail": f"boş disk {disk} GB"})
        if out:
            self._emit(ResourceEvents.BOTTLENECK, {"count": len(out)})
        return out

    def recommendations(self, actor: str) -> list[str]:
        """Deterministik yükseltme/optimizasyon önerileri (darboğaz + aşılmış bütçe)."""
        self._authorize(actor)
        recs = []
        for b in self.bottlenecks(actor):
            if b["resource"] == "ram":
                recs.append("RAM darboğazı: model boyutunu küçült / OLLAMA_MAX_LOADED_MODELS=1 / RAM yükselt.")
            elif b["resource"] == "cpu":
                recs.append("CPU darboğazı: paralel iş yükünü azalt veya çekirdek yükselt.")
            elif b["resource"] == "disk":
                recs.append("Disk darboğazı: geçici dosyaları temizle veya disk genişlet.")
        for bd in self._repo.all_budgets():
            if not bd.within:
                recs.append(f"'{bd.name}' bütçesi aşıldı ({bd.consumed}/{bd.limit} {bd.unit}): "
                            f"tüketimi azalt veya limiti gözden geçir.")
        return recs or ["Belirgin darboğaz/bütçe aşımı yok."]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"budgets": self._repo.budget_count(),
                "exceeded_budgets": sum(1 for b in self._repo.all_budgets() if not b.within),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return resources_contract()

    # ------------------------------------------------------------------ #
    def _current(self) -> dict:
        snap = dict(self._probe() or {})
        self._derive(snap)
        return snap

    def _require_budget(self, name: str) -> Budget:
        b = self._repo.get_budget(name)
        if b is None:
            raise NotFoundError(f"Bütçe bulunamadı: {name}")
        return b

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' kaynak erişimi için yetkili değil")

    def _authorize_admin(self, actor: str) -> None:
        if not self._cfg.is_admin(actor):
            raise UnauthorizedError(f"'{actor}' bütçe yönetimi için yetkili değil (admin gerekir)")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' bütçe tüketimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
