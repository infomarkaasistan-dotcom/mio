"""MIO Core · Application Service — CLI ve HTTP adapter'larının PAYLAŞTIĞI public-sözleşme dispatch yüzeyi.

**İş mantığı burada YOKTUR** — tüm mantık domainlerde/runtime'dadır (Madde 15/16). Bu katman yalnız ince bir
yönlendirmedir: adı verilen public operasyonu ilgili domaine/runtime'a delege eder. Böylece CLI ve HTTP **aynı**
sözleşmeleri kullanır; kod kopyalanmaz. Güvenlik: yalnız sözleşmeli (contract'lı) domainler ve public operasyonlar
erişilebilir; `mio.close()` gibi runtime iç yüzeyi bu katmandan çağrılamaz."""

from __future__ import annotations

from typing import Any, Optional

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


def connect_env(mio, *, workspace: Optional[str] = None) -> dict[str, Any]:
    """env'e göre gerçek connector adapter'larını bağlar (Application Service — arayüzler bunu çağırır)."""
    from mio_core.connectors.adapters import register_from_env
    ws = workspace or getattr(mio, "_workspace", ".mio")
    summary = register_from_env(mio.connectors, workspace=ws)
    if "ollama" in summary.get("registered", []):
        hw = mio.hardware.report()
        summary["hardware_warnings"] = hw["warnings"]
        summary["hardware_recommendations"] = hw["recommendations"]
    return summary


# ---- Monitoring yüzeyi — CLI+HTTP ortak ----
def prometheus_metrics(mio) -> str:
    """Prometheus text exposition (scrape). Çekirdek metriklerini Monitoring Adapter formatlar."""
    return mio.monitoring.prometheus()


def otlp_metrics(mio) -> dict[str, Any]:
    """OTLP/HTTP-JSON metrics payload."""
    return mio.monitoring.otlp_metrics()


# ---- Hardware Diagnostics yüzeyi — CLI+HTTP ortak ----
def hardware_report(mio) -> dict[str, Any]:
    """CPU/RAM/GPU/VRAM/CUDA/Ollama + CPU-vs-GPU çıkarım tespiti + uyarı/öneri."""
    return mio.hardware.report()


# ---- Diagnose / Executive / Models — arayüz-agnostik DTO'lar (CLI/HTTP/UI/Voice AYNI) ----
def diagnose(mio) -> dict[str, Any]:
    """Tam sağlık denetimi DTO'su: her bileşen için status + genel Executive Score. İş mantığı runtime'da."""
    r = mio.readiness()
    checks = r.get("checks", {})
    hw = mio.hardware.report()
    conn = mio.connector_registry.stats()
    components = []

    def _add(name: str, ok: bool, detail: str = "") -> None:
        components.append({"component": name, "status": "ok" if ok else "attention", "detail": detail})

    _add("Executive Core", not mio._closed, "runtime açık" if not mio._closed else "kapalı")
    _add("Event Bus", checks.get("event_bus", {}).get("ok", False))
    _add("Persistence", checks.get("persistence_stores", {}).get("ok", False),
         f"{checks.get('persistence_stores', {}).get('count', 0)} store")
    _add("Domains", checks.get("domains", {}).get("ok", False),
         f"{checks.get('domains', {}).get('ready', 0)}/{checks.get('domains', {}).get('total', 0)} hazır")
    _add("Resilience", checks.get("resilience", {}).get("ok", False))
    _add("Workspace", checks.get("workspace_writable", {}).get("ok", False))
    _add("Hardware / GPU", hw.get("gpu_available", False),
         hw["gpus"][0]["name"] if hw.get("gpus") else "GPU yok")
    _add("CUDA", hw.get("cuda", {}).get("available", False), hw.get("cuda", {}).get("version") or "")
    _add("Ollama", hw.get("ollama", {}).get("reachable", False), hw.get("ollama", {}).get("version") or "")
    _add("Connectors", True, f"{conn.get('connectors', 0)} bağlı, {conn.get('unhealthy', 0)} sağlıksız")

    ok_count = sum(1 for c in components if c["status"] == "ok")
    score = round(100 * ok_count / max(1, len(components)))
    return {"score": score, "max": 100, "ready": r.get("ready", False),
            "verdict": "System Ready" if score >= 80 else ("Degraded" if score >= 50 else "Attention Needed"),
            "components": components, "warnings": hw.get("warnings", []),
            "recommendations": hw.get("recommendations", [])}


def executive_summary(mio) -> dict[str, Any]:
    """Executive workspace DTO'su: kimlik + brain/domain/connector sayıları + sistem güveni + öneriler."""
    diag = diagnose(mio)
    who = mio.who_am_i() if hasattr(mio, "who_am_i") else {}
    return {
        "identity": {"name": who.get("name", "MIO"), "role": who.get("role", "Executive")},
        "system_confidence": diag["verdict"], "executive_score": diag["score"],
        "domains": len(PUBLIC_DOMAINS),
        "brains": len(getattr(mio.brains, "all", lambda: [])()) if hasattr(mio, "brains") else 0,
        "connectors": mio.connector_registry.stats().get("connectors", 0),
        "pending_decisions": mio.connector_registry.stats().get("unhealthy", 0),
        "inference": {"prepared": bool((mio.inference_status or {}).get("ready")),
                      "model": (mio.inference_status or {}).get("selected_model")},
        "recommended_actions": diag["recommendations"][:3],
        "warnings": diag["warnings"][:3],
    }


def models_overview(mio) -> dict[str, Any]:
    """Model workspace DTO'su: kurulu/yüklü modeller + CPU/GPU yerleşim + VRAM'e göre öneri."""
    li = mio.local_inference
    installed = li.installed_models()
    loaded = li.loaded_models()
    rec = mio.hardware.recommend_model(installed) if installed else {"recommended": None, "candidates": []}
    return {"installed": installed, "loaded": loaded,
            "recommended": rec.get("recommended"), "vram_free_mb": rec.get("vram_free_mb", 0),
            "candidates": rec.get("candidates", []), "ollama_reachable": li.ollama_reachable()}


# ---- Local Inference (MIO ortamı yönetir) yüzeyi — CLI+HTTP ortak ----
def inference_analyze(mio) -> dict[str, Any]:
    """Salt-okunur: donanım + Ollama + kurulu/yüklü modeller + CPU/GPU yerleşim."""
    return mio.local_inference.analyze()


def inference_ensure_ready(mio, *, approve=frozenset(), auto_pull: bool = True,
                           run_test: bool = True) -> dict[str, Any]:
    """Ortamı hazırla: uygun modeli seç, fazlalıkları durdur, eksikse indir, test et. SİLME/KURULUM onay ister."""
    return mio.local_inference.ensure_ready(approve=frozenset(approve), auto_pull=auto_pull, run_test=run_test)


__all__ = [
    "NotFound", "BadRequest", "PUBLIC_DOMAINS",
    "list_domains", "domain_contract", "domain_stats", "metrics", "readiness", "health", "events", "call",
    "connectors_overview", "capabilities_catalog", "execute_capability", "connect_env",
    "prometheus_metrics", "otlp_metrics", "hardware_report",
    "inference_analyze", "inference_ensure_ready",
    "diagnose", "executive_summary", "models_overview",
]
