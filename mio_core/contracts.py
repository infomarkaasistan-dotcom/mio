"""MIO Core · Contract Versioning (Platform Invariant §2) — Capability + Event sözleşmeleri versiyonlu.

Sözleşmeler versiyonlu ve GERİYE-UYUMLULUK denetlenebilir olmalı. Bu modül: bir Capability'nin public
sözleşmesini üretir, imzasını (drift tespiti) hesaplar, iki sürümün uyumluluğunu deterministik kontrol eder;
Event tipleri için sürüm kaydı tutar. Yeni kural eklemez — mevcut invariant'ı makine-uygulanır yapar."""

from __future__ import annotations

import hashlib
from typing import Any

from mio_core.capability import Capability

__all__ = ["capability_contract", "contract_signature", "contracts_compatible",
           "version_tuple", "EventContracts"]


def capability_contract(cap: Capability) -> dict[str, Any]:
    """Bir yeteneğin PUBLIC sözleşmesi (Domain'ler yalnız bunu görür — Bounded Context §4)."""
    schema = cap.parameters or {}
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    return {
        "name": cap.name, "version": cap.contract_version, "category": cap.category,
        "risk": cap.risk_level, "required_permissions": sorted(cap.required_permissions),
        "required_params": sorted(schema.get("required", []) if isinstance(schema, dict) else []),
        "params": sorted(props.keys()),
    }


def contract_signature(cap: Capability) -> str:
    """Sözleşme ŞEKLİNİN imzası (sürümden bağımsız). Değişirse ama version artmazsa → drift."""
    c = capability_contract(cap)
    blob = "|".join([c["name"], c["risk"], ",".join(c["required_permissions"]),
                     ",".join(c["required_params"]), ",".join(c["params"])])
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def version_tuple(v: str) -> tuple:
    parts = (v or "0").split(".")
    return tuple(int(p) if p.isdigit() else 0 for p in (parts + ["0", "0"])[:3])


def contracts_compatible(old: dict, new: dict) -> bool:
    """Geriye-uyum (Priority Order §1 madde 4): aynı isim, major sürüm artmadı, kaldırılan zorunlu
    parametre/izin yok, risk yükselmedi."""
    if old["name"] != new["name"]:
        return False
    if version_tuple(new["version"])[0] > version_tuple(old["version"])[0]:
        return False                                     # major bump → breaking
    if set(old["required_params"]) - set(new["required_params"]):
        return False                                     # kaldırılan zorunlu parametre
    if set(old["required_permissions"]) - set(new["required_permissions"]):
        return False
    _risk = {"low": 0, "medium": 1, "high": 2}
    return _risk.get(new["risk"], 1) <= _risk.get(old["risk"], 1)   # risk yükselmesin


class EventContracts:
    """Event tipleri için sürüm kaydı. Publish'e sürüm iliştirilir; şema evrimi denetlenebilir."""

    def __init__(self) -> None:
        self._versions: dict[str, str] = {}

    def register(self, event_type: str, version: str = "1.0.0") -> None:
        self._versions[event_type] = version

    def version(self, event_type: str) -> str:
        return self._versions.get(event_type, "1.0.0")

    def all(self) -> dict[str, str]:
        return dict(self._versions)
