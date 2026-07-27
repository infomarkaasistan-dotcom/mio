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
    """Yapılandırmaya göre gerçek connector adapter'larını bağlar (Application Service — arayüzler bunu çağırır).

    KÖK NEDEN DÜZELTMESİ: `mio.config` (=.env + os.environ) kullanılır — artık `.env`'deki `LLM_ENABLED=true`,
    `SMTP_HOST`, `OPENAI_API_KEY` vb. GERÇEKTEN okunur (önceden yalnız os.environ'a bakılıyordu)."""
    from mio_core.connectors.adapters import register_from_env
    ws = workspace or getattr(mio, "_workspace", ".mio")
    summary = register_from_env(mio.connectors, env=mio.config.as_dict(), workspace=ws)
    if "ollama" in summary.get("registered", []):
        hw = mio.hardware.report()
        summary["hardware_warnings"] = hw["warnings"]
        summary["hardware_recommendations"] = hw["recommendations"]
    return summary


def config_diagnostics(mio) -> dict[str, Any]:
    """Yapılandırma teşhisi DTO'su (sır değerleri maskeli): hangi anahtar nereden geliyor + LLM/Ollama durumu."""
    diag = mio.config.diagnostics()
    diag["llm_enabled"] = mio.config.get_bool("LLM_ENABLED", False)
    diag["ollama_reachable"] = mio.local_inference.ollama_reachable()
    return diag


# ---- Business Workspace yüzeyi (çoklu izole işletme; CLI/UI ortak) ----
def business_list(mio) -> list[dict[str, Any]]:
    return mio.business.list()


def business_create(mio, name: str, *, business_type: str = "personal",
                    objectives: Optional[list] = None) -> dict[str, Any]:
    return mio.business.create(name, business_type=business_type, objectives=objectives)


def business_get(mio, business_id: str) -> dict[str, Any]:
    b = mio.business.get(business_id)
    if b is None:
        raise NotFound(f"işletme bulunamadı: {business_id}")
    return b


def business_delete(mio, business_id: str, *, purge: bool = False) -> dict[str, Any]:
    return mio.business.delete(business_id, purge=purge)


def business_stats(mio) -> dict[str, Any]:
    return mio.business.stats()


# ---- Conversational yüzeyi (doğal dil → mevcut işlemler; CLI/UI/Voice ortak) ----
def converse(mio, text: str, *, actor: str = "owner") -> dict[str, Any]:
    """Doğal dil isteğini Executive orkestratörüne verir → mevcut appservice işlemlerine yönlendirir.

    Bu bir orkestrasyon yüzeyidir (yeni mimari değil); iş mantığı domainlerde/Executive'te. LLM danışman, karar
    verici değil. {intent, response, data} döner (Dashboard aynı DTO'yu kart/balon olarak render eder)."""
    return mio.conversational.handle(text, actor=actor)


# ---- HTTP server lifecycle + Workspace yüzeyi (CLI/UI ortak) ----
def server_start(mio, *, host: str = "127.0.0.1", port: int = 8080) -> dict[str, Any]:
    return mio.http_server.start(host=host, port=int(port))


def server_stop(mio) -> dict[str, Any]:
    return mio.http_server.stop()


def server_status(mio) -> dict[str, Any]:
    return mio.http_server.status()


def workflow_create(mio, name: str, tasks: list, *, actor: str = "owner") -> dict[str, Any]:
    return mio.workflow.create_workflow(actor, name, tasks)


def workflow_list(mio, *, actor: str = "owner", status: Optional[str] = None) -> list[dict[str, Any]]:
    return mio.workflow.list_workflows(actor, status=status)


def workflow_get(mio, workflow_id: str, *, actor: str = "owner") -> dict[str, Any]:
    return mio.workflow.get_workflow(actor, workflow_id)


def workflow_plan(mio, workflow_id: str, *, actor: str = "owner") -> dict[str, Any]:
    return mio.workflow.plan(actor, workflow_id)


def workflow_run(mio, workflow_id: str, *, actor: str = "owner", approve: bool = False,
                 max_steps: int = 100) -> dict[str, Any]:
    """EXECUTIVE KÖPRÜSÜ: DAG'ı yürütür. Ready görevleri ConnectorManager ile çalıştırır, checkpoint günceller.

    Human-approval görevi (blocked_approval) `approve=True` ile onaylanır (Madde 24). Görev capability'si yoksa
    (salt-mantık görevi) doğrudan tamamlanır. connector_unavailable → görev fail (workflow durur, resume mümkün)."""
    mio.workflow.start(actor, workflow_id)
    executed = []
    for _ in range(int(max_steps)):
        wf = mio.workflow.get_workflow(actor, workflow_id)
        if wf["status"] in ("completed", "failed"):
            break
        # onay bekleyen görevleri (izin verildiyse) onayla
        if approve:
            for t in wf["tasks"]:
                if t["status"] == "blocked_approval":
                    mio.workflow.approve_task(actor, workflow_id, t["id"])
        ready = mio.workflow.ready_tasks(actor, workflow_id)
        if not ready:
            break                                     # ready yok (onay bekliyor ya da bitti)
        for t in ready:
            if t.get("capability"):
                outcome = mio.connectors.execute(t["capability"], t.get("request", {}), actor=actor,
                                                 user_approved=approve)
                if outcome.get("status") == "executed":
                    mio.workflow.complete_task(actor, workflow_id, t["id"], result=outcome.get("result", {}))
                    executed.append({"task": t["name"], "status": "executed"})
                else:
                    mio.workflow.fail_task(actor, workflow_id, t["id"], error=outcome.get("status", "failed"))
                    executed.append({"task": t["name"], "status": outcome.get("status")})
            else:
                mio.workflow.complete_task(actor, workflow_id, t["id"])   # salt-mantık görevi
                executed.append({"task": t["name"], "status": "completed"})
    final = mio.workflow.get_workflow(actor, workflow_id)
    return {"workflow_id": workflow_id, "status": final["status"], "progress": final["progress"],
            "executed": executed}


def workspace_info(mio) -> dict[str, Any]:
    """Workspace teşhisi: yol + boyut + domain veritabanı sayısı + disk (deterministik, salt-okunur)."""
    import os
    import shutil
    ws = getattr(mio, "_workspace", "") or "."
    dbs, total = [], 0
    try:
        for fn in sorted(os.listdir(ws)):
            if fn.endswith(".db"):
                sz = os.path.getsize(os.path.join(ws, fn))
                dbs.append({"name": fn, "size": sz})
                total += sz
    except Exception:  # noqa: BLE001
        pass
    disk = shutil.disk_usage(ws) if os.path.isdir(ws) else None
    return {"workspace": ws, "databases": len(dbs), "total_bytes": total, "files": dbs,
            "disk_free_mb": (disk.free // (1024 * 1024)) if disk else None}


# ---- MCP Manager yüzeyi — CLI/HTTP/UI ortak (iş mantığı mcp_management domaininde) ----
def mcp_list(mio, *, actor: str = "owner") -> list[dict[str, Any]]:
    return mio.mcp_management.list_servers(actor)


def mcp_status(mio, *, actor: str = "owner") -> dict[str, Any]:
    return {"health": mio.mcp_management.health_check(actor), "stats": mio.mcp_management.stats()}


def mcp_doctor(mio, *, actor: str = "owner") -> dict[str, Any]:
    """Tam MCP teşhisi: sunucular + discover + health + stats (kompozit; alt-çağrılar domaine delege)."""
    return {"servers": mio.mcp_management.list_servers(actor),
            "discovery": mio.mcp_management.discover(actor),
            "health": mio.mcp_management.health_check(actor),
            "stats": mio.mcp_management.stats()}


def mcp_discover(mio, *, actor: str = "owner") -> dict[str, Any]:
    return mio.mcp_management.discover(actor)


def mcp_stats(mio) -> dict[str, Any]:
    return mio.mcp_management.stats()


def mcp_info(mio, server_id: str, *, actor: str = "owner") -> dict[str, Any]:
    return mio.mcp_management.describe(actor, server_id)


def mcp_register(mio, name: str, *, actor: str = "owner", **kwargs) -> dict[str, Any]:
    """MCP sunucusu kaydet (install). name zorunlu; url/transport/command kwargs olarak geçer."""
    return mio.mcp_management.register_server(actor, name, **kwargs)


def mcp_remove(mio, server_id: str, *, actor: str = "owner") -> dict[str, Any]:
    mio.mcp_management.remove_server(actor, server_id)
    return {"removed": server_id}


def mcp_activate(mio, *, actor: str = "owner") -> dict[str, Any]:
    """Güvenilir MCP sunucularının capability'lerini platforma bağla (enable)."""
    return mio.mcp_management.activate(actor)


def mcp_trust(mio, server_id: str, level: str, *, actor: str = "owner") -> dict[str, Any]:
    return mio.mcp_management.set_trust(actor, server_id, level)


def mcp_contract(mio) -> dict[str, Any]:
    return mio.mcp_management.contract()


# ---- Presentation yüzeyi + Executive köprüsü (domain NİYET üretir; Executive YÜRÜTÜR) ----
def presentation_create(mio, title: str, *, actor: str = "owner", **kwargs) -> dict[str, Any]:
    return mio.presentation.create_script(actor, title, **kwargs)


def presentation_outline(mio, title: str, outline: list, *, actor: str = "owner", **kwargs) -> dict[str, Any]:
    return mio.presentation.outline_to_script(actor, title, outline, **kwargs)


def presentation_plan(mio, script_id: str, *, actor: str = "owner") -> dict[str, Any]:
    """Domain'in ürettiği niyet (CapabilityIntent) listesi — YÜRÜTME YOK (yalnız plan)."""
    return mio.presentation.plan_delivery(actor, script_id)


def presentation_list(mio, *, actor: str = "owner", kind: Optional[str] = None) -> list[dict[str, Any]]:
    return mio.presentation.list_scripts(actor, kind=kind)


def presentation_deliver(mio, script_id: str, *, actor: str = "owner", approve: bool = False) -> dict[str, Any]:
    """EXECUTIVE KÖPRÜSÜ: Presentation niyetlerini ConnectorManager ile YÜRÜTÜR (domain yürütmez — katman ayrımı).

    ConnectorManager yalnız burada (Executive/Application Service katmanı) çağrılır. Yüksek-risk niyet onaysızsa
    yürütülmez (Madde 24 → outcome requires_approval); connector yoksa connector_unavailable (çökmez)."""
    plan = mio.presentation.plan_delivery(actor, script_id)
    results = []
    for intent in plan["intents"]:
        needs = intent.get("requires_approval", False)
        outcome = mio.connectors.execute(intent["capability"], intent.get("request", {}),
                                         actor=actor, user_approved=(approve if needs else False))
        results.append({"capability": intent["capability"], "label": intent.get("label", ""),
                        "requires_approval": needs, "outcome": outcome})
    executed = sum(1 for r in results if r["outcome"].get("status") == "executed")
    return {"script_id": script_id, "kind": plan.get("kind"), "total": len(results),
            "executed": executed, "results": results}


# ---- Conversation yüzeyi + Executive köprüsü (domain NİYET üretir; Executive YÜRÜTÜR) ----
def conversation_receive(mio, user_handle: str, text: str, *, actor: str = "owner",
                         platform_ref: Optional[dict] = None) -> dict[str, Any]:
    """Mesaj işle (sınıflandır + moderasyon TESPİTİ). Cevap göndermez — Executive karar verir."""
    return mio.conversation.receive(actor, user_handle, text, platform_ref=platform_ref)


def conversation_queue(mio, *, actor: str = "owner", limit: int = 20) -> list[dict[str, Any]]:
    return mio.conversation.queue(actor, limit=limit)


def conversation_summary(mio, *, actor: str = "owner") -> dict[str, Any]:
    return mio.conversation.summarize(actor)


def conversation_reply(mio, message_id: str, text: str, *, actor: str = "owner", private: bool = False,
                       approve: bool = False) -> dict[str, Any]:
    """EXECUTIVE KÖPRÜSÜ: cevap niyetini ConnectorManager ile YÜRÜTÜR (domain yürütmez). conversation.reply."""
    intent = mio.conversation.plan_reply(actor, message_id, text, private=private)
    needs = intent.get("requires_approval", False)
    outcome = mio.connectors.execute(intent["capability"], intent.get("request", {}),
                                     actor=actor, user_approved=(approve if needs else False))
    if outcome.get("status") == "executed":
        mio.conversation.mark_answered(actor, message_id)
    return {"intent": intent, "outcome": outcome}


def conversation_moderate(mio, message_id: str, action: str, *, actor: str = "owner",
                          approve: bool = False) -> dict[str, Any]:
    """EXECUTIVE KÖPRÜSÜ: moderasyon niyetini YÜRÜTÜR. Yüksek-risk (delete/timeout/ban/pin) onaysız yürütülmez."""
    intent = mio.conversation.moderation_intent(actor, message_id, action)
    needs = intent.get("requires_approval", False)
    outcome = mio.connectors.execute(intent["capability"], intent.get("request", {}),
                                     actor=actor, user_approved=(approve if needs else False))
    return {"intent": intent, "outcome": outcome}


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


# ---- Otonom Görev yüzeyi (hedef → CEO böler → brain-destekli agent'lar → çıktı → rapor) ----
def mission_run(mio, goal_text: str, *, business_id: Optional[str] = None, actor: str = "owner",
                max_steps: int = 5) -> dict[str, Any]:
    """Bir hedefi otonom yürütür (LLM karar vermez — brain'ler çıktı üretir, Executive karar verir)."""
    return mio.mission.run(goal_text, business_id=business_id, actor=actor, max_steps=int(max_steps))


# ---- MCP Kataloğu yüzeyi ("tüm MCP'leri kur; kullanıcı yalnız yetki/anahtar verir") ----
def mcp_install_catalog(mio, *, actor: str = "owner") -> dict[str, Any]:
    """Bilinen MCP sunucularını UNTRUSTED kaydeder (idempotent; Madde 24 — yetki kullanıcıya ait)."""
    from mio_core import mcp_catalog
    return mcp_catalog.install_catalog(mio, actor=actor)


def mcp_catalog_status(mio, *, actor: str = "owner") -> list[dict[str, Any]]:
    """Katalog + canlı kayıt durumu (arayüz için): her MCP'nin gerekli anahtarları, risk, trust, enabled."""
    from mio_core import mcp_catalog
    return mcp_catalog.catalog_status(mio, actor=actor)


# ---- CEO Experience yüzeyi (intent→plan→delegate→execute→report) — CLI/HTTP/conversational ortak ----
def ceo_direct(mio, goal_text: str, *, horizon_days: int = 30, steps: Optional[list] = None,
               actor: str = "owner") -> dict[str, Any]:
    """Sahibin stratejik niyetini Executive hedefi + Planning planına dönüştürür (yürütmez)."""
    return mio.ceo.direct(goal_text, horizon_days=int(horizon_days), steps=steps, actor=actor)


def ceo_delegate(mio, plan_id: str, *, actor: str = "owner", approve: bool = False) -> dict[str, Any]:
    """Planning adımlarını Multi-Agent görevlerine devreder (execute). Yüksek-risk görev onay ister (Madde 24)."""
    return mio.ceo.delegate(plan_id, actor=actor, approve=approve)


def ceo_report(mio, *, actor: str = "owner") -> dict[str, Any]:
    """Konsolide yönetim panosu (Dashboard DTO): Executive + Planning + Multi-Agent + Business + tanı."""
    return mio.ceo.report(actor=actor)


# ---- Agent yönetimi yüzeyi (mevcut multi_agent'a delege — yeni sistem YOK) ----
def agent_list(mio, *, actor: str = "owner") -> list[dict[str, Any]]:
    return mio.multi_agent.list_agents(actor)


def agent_register(mio, name: str, *, role: str = "worker", capabilities: Optional[list] = None,
                   max_load: int = 3, actor: str = "owner") -> dict[str, Any]:
    return mio.multi_agent.register_agent(actor, name, role=role,
                                          capabilities=list(capabilities or []), max_load=int(max_load))


def agent_tasks(mio, *, actor: str = "owner", status: Optional[str] = None) -> list[dict[str, Any]]:
    return mio.multi_agent.list_tasks(actor, status=status)


def agent_task_approve(mio, task_id: str, *, actor: str = "owner") -> dict[str, Any]:
    return mio.multi_agent.approve_task(actor, task_id)


def agent_stats(mio, *, actor: str = "owner") -> dict[str, Any]:
    return mio.multi_agent.stats()


__all__ = [
    "NotFound", "BadRequest", "PUBLIC_DOMAINS",
    "list_domains", "domain_contract", "domain_stats", "metrics", "readiness", "health", "events", "call",
    "connectors_overview", "capabilities_catalog", "execute_capability", "connect_env", "config_diagnostics",
    "prometheus_metrics", "otlp_metrics", "hardware_report",
    "inference_analyze", "inference_ensure_ready",
    "diagnose", "executive_summary", "models_overview", "config_diagnostics",
    "mcp_list", "mcp_status", "mcp_doctor", "mcp_discover", "mcp_stats", "mcp_info",
    "mcp_register", "mcp_remove", "mcp_activate", "mcp_trust", "mcp_contract",
    "presentation_create", "presentation_outline", "presentation_plan", "presentation_list",
    "presentation_deliver",
    "conversation_receive", "conversation_queue", "conversation_summary", "conversation_reply",
    "conversation_moderate",
    "server_start", "server_stop", "server_status", "workspace_info",
    "workflow_create", "workflow_list", "workflow_get", "workflow_plan", "workflow_run",
    "converse", "business_list", "business_create", "business_get", "business_delete", "business_stats",
    "ceo_direct", "ceo_delegate", "ceo_report",
    "agent_list", "agent_register", "agent_tasks", "agent_task_approve", "agent_stats",
    "mcp_install_catalog", "mcp_catalog_status", "mission_run",
]
