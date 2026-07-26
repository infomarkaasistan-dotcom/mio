"""MIO Core · Application Service — CLI ve HTTP adapter'larının PAYLAŞTIĞI public-sözleşme dispatch yüzeyi.

**İş mantığı burada YOKTUR** — tüm mantık domainlerde/runtime'dadır (Madde 15/16). Bu katman yalnız ince bir
yönlendirmedir: adı verilen public operasyonu ilgili domaine/runtime'a delege eder. Böylece CLI ve HTTP **aynı**
sözleşmeleri kullanır; kod kopyalanmaz. Güvenlik: yalnız sözleşmeli (contract'lı) domainler ve public operasyonlar
erişilebilir; `mio.close()` gibi runtime iç yüzeyi bu katmandan çağrılamaz."""

from __future__ import annotations

from typing import Any

from mio_core.runtime import _READINESS_DOMAINS

# HTTP/CLI adapter'larının statü eşlemesi için hafif hata tipleri (iş mantığı değil).
class NotFound(Exception):
    """İstenen domain/operasyon yok (adapter → 404 / CLI → 2)."""


class BadRequest(Exception):
    """Geçersiz istek biçimi (adapter → 400 / CLI → 2)."""


# Sözleşmeli (public) domainler — generic yüzeyin izin verdiği tek küme (güvenlik sınırı).
PUBLIC_DOMAINS = frozenset(_READINESS_DOMAINS)


def _require_domain(mio, name: str):
    if name not in PUBLIC_DOMAINS:
        raise NotFound(f"domain bulunamadı: {name}")
    obj = getattr(mio, name, None)
    if obj is None or not hasattr(obj, "contract"):
        raise NotFound(f"domain bulunamadı: {name}")
    return obj


# ---- inceleme (read) yüzeyi ----
def list_domains(mio) -> list[dict[str, Any]]:
    out = []
    for name in _READINESS_DOMAINS:
        obj = getattr(mio, name, None)
        if obj is None or not hasattr(obj, "contract"):
            continue
        try:
            c = obj.contract()
            out.append({"domain": name, "version": c.get("version"),
                        "operations": len(c.get("operations", [])),
                        "description": (c.get("description", "") or "")[:80]})
        except Exception as exc:  # noqa: BLE001
            out.append({"domain": name, "error": str(exc)[:80]})
    return out


def domain_contract(mio, name: str) -> dict[str, Any]:
    return _require_domain(mio, name).contract()


def domain_stats(mio, name: str) -> dict[str, Any]:
    obj = _require_domain(mio, name)
    if not hasattr(obj, "stats"):
        raise NotFound(f"{name}.stats() yok")
    return obj.stats()


def metrics(mio) -> dict[str, Any]:
    return mio.metrics()


def readiness(mio) -> dict[str, Any]:
    return mio.readiness()


def health(mio) -> dict[str, Any]:
    return mio.health()


def events(mio, limit: int = 20) -> list[dict[str, Any]]:
    return [{"type": e.get("type"), "data": e.get("data")}
            for e in mio.bus.history(limit=int(limit))]


# ---- eylem (call) yüzeyi — reflektif operasyon çağrısı ----
def call(mio, domain: str, operation: str, kwargs: dict) -> Any:
    """Bir domain public operasyonunu delege eder. Domain'in kendi authz/validation'ı (Madde 24 vb.) YÜRÜRLÜKTE.

    Yükseltir: NotFound (domain/op yok) · BadRequest (özel metod / kwargs biçimi) · domain istisnaları (aynen)."""
    obj = _require_domain(mio, domain)
    if operation.startswith("_"):
        raise BadRequest("özel (underscore) operasyon çağrılamaz")
    if not isinstance(kwargs, dict):
        raise BadRequest('kwargs bir nesne olmalı, ör: {"actor":"owner","name":"S"}')
    fn = getattr(obj, operation, None)
    if not callable(fn):
        raise NotFound(f"operasyon bulunamadı: {domain}.{operation}")
    return fn(**kwargs)


# ---- Capability Adapter Layer (Connector) yüzeyi — CLI+HTTP ortak ----
def connectors_overview(mio) -> list[dict[str, Any]]:
    return mio.connector_registry.overview()


def capabilities_catalog(mio) -> dict[str, Any]:
    return {"capabilities": mio.connector_registry.capabilities(),
            "stats": mio.connector_registry.stats()}


def execute_capability(mio, capability: str, request: Any, *, actor: str = "owner",
                       user_approved: bool = False) -> dict[str, Any]:
    """Capability'yi Connector Manager üzerinden çalıştırır (Executive isimle değil capability ile çağırır).

    ASLA raise ETMEZ — connector yoksa dürüst connector_unavailable döner (Madde 8; sistem çökmez)."""
    if request is None:
        request = {}
    if not isinstance(request, dict):
        raise BadRequest('request bir nesne olmalı, ör: {"to":"a@b.com","subject":"..."}')
    return mio.connectors.execute(capability, request, actor=actor, user_approved=user_approved)


__all__ = [
    "NotFound", "BadRequest", "PUBLIC_DOMAINS",
    "list_domains", "domain_contract", "domain_stats", "metrics", "readiness", "health", "events", "call",
    "connectors_overview", "capabilities_catalog", "execute_capability",
]
