"""MIO Core · Multi-Agent Domain (Faz 5 · Domain 36) — üretim testleri: unit+integration+smoke.

Anayasa özü: **Executive tek karar verici; agent'lar DETERMİNİSTİK atamayla iş yürütür, tek başına karar VERMEZ.**
Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik executor üzerinden. Deterministik atama,
yetenek eşleşmesi, kapasite/yük, DÜRÜST no_agent & no_connector, Madde 24 onay kapısı, events doğrulanır."""

import pytest

from mio_core.domains.multi_agent import (
    AgentStatus,
    MultiAgentDomain,
    MultiAgentEvents,
    MultiAgentRepository,
    NotFoundError,
    Risk,
    TaskStatus,
    UnauthorizedError,
    ValidationError,
    classify_risk,
)
from mio_core.events import EventBus


def _build():
    repo = MultiAgentRepository(":memory:")
    bus = EventBus(record=True)
    dom = MultiAgentDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def ma():
    return _build()


# ---- UNIT: risk + validation + authz ----
def test_risk_validation_authz(ma):
    d, _r, _b = ma
    assert classify_risk("summarize notes") == Risk.LOW
    assert classify_risk("deploy to prod") == Risk.HIGH       # tehlikeli işaret
    assert classify_risk("x", declared=Risk.HIGH) == Risk.HIGH
    with pytest.raises(UnauthorizedError):
        d.register_agent("Perception", "A")                   # reader ama writer değil
    with pytest.raises(ValidationError):
        d.register_agent("owner", "A", trust=2.0)             # 0..1 dışı
    with pytest.raises(ValidationError):
        d.register_agent("owner", "A", max_load=0)


# ---- INTEGRATION: DETERMİNİSTİK atama (yüksek güven kazanır) ----
def test_deterministic_assignment_by_trust(ma):
    d, _r, bus = ma
    lo = d.register_agent("owner", "lo", capabilities=["code"], trust=0.4)
    hi = d.register_agent("owner", "hi", capabilities=["code"], trust=0.9)
    d.register_executor(lo["id"], lambda ctx: {"by": "lo"})
    d.register_executor(hi["id"], lambda ctx: {"by": "hi"})
    t = d.submit_task("owner", "write function", required_capabilities=["code"])
    assert t["status"] == TaskStatus.COMPLETED and t["assigned_agent"] == hi["id"]   # güven baskın
    assert t["result"] == {"by": "hi"}
    assert any(e["type"] == MultiAgentEvents.TASK_ASSIGNED for e in bus.history())
    # deterministik: aynı koşul → aynı agent
    t2 = d.submit_task("owner", "write another", required_capabilities=["code"])
    assert t2["assigned_agent"] == hi["id"]


# ---- INTEGRATION: yetenek eşleşmesi + kapasite/yük ----
def test_capability_and_capacity(ma):
    d, _r, _b = ma
    # yalnız 'design' yeteneği olan tek agent, kapasite 1
    a = d.register_agent("owner", "designer", capabilities=["design"], trust=0.8, max_load=1)
    # executor bloklayıcı: WORKING'de kalan bir görev kapasiteyi tüketsin diye çağrı içinde başka görev submit
    seen = {}

    def busy_executor(ctx):
        # bu executor çalışırken ikinci görev submit edilirse agent doludur (spare 0) → no_agent beklenir
        seen["inner"] = d.submit_task("owner", "second design", required_capabilities=["design"])
        return {"ok": True}

    d.register_executor(a["id"], busy_executor)
    first = d.submit_task("owner", "first design", required_capabilities=["design"])
    assert first["status"] == TaskStatus.COMPLETED
    # dıştaki görev çalışırken agent doluydu → içteki görev uygun agent bulamadı (dürüst)
    assert seen["inner"]["status"] == TaskStatus.NO_AGENT
    # gerekli yeteneğe kimse sahip değilse → no_agent
    none_match = d.submit_task("owner", "translate", required_capabilities=["nlp"])
    assert none_match["status"] == TaskStatus.NO_AGENT


# ---- INTEGRATION: agent atandı ama executor yok → DÜRÜST no_connector ----
def test_no_connector_when_no_executor(ma):
    d, _r, bus = ma
    a = d.register_agent("owner", "worker", capabilities=["build"])
    task = d.submit_task("owner", "build image", required_capabilities=["build"])
    assert task["status"] == TaskStatus.NO_CONNECTOR and task["assigned_agent"] == a["id"]
    assert task["result"] == {}
    assert any(e["type"] == MultiAgentEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: executor hatası → failed ----
def test_executor_failure(ma):
    d, _r, _b = ma
    a = d.register_agent("owner", "w", capabilities=["x"])
    d.register_executor(a["id"], lambda ctx: (_ for _ in ()).throw(RuntimeError("uzak hata")))
    task = d.submit_task("owner", "do x", required_capabilities=["x"])
    assert task["status"] == TaskStatus.FAILED and "uzak hata" in task["error"]


# ---- INTEGRATION: yüksek-risk görev → requires_approval (Madde 24) ----
def test_high_risk_requires_approval(ma):
    d, _r, bus = ma
    a = d.register_agent("owner", "deployer", capabilities=["deploy"])
    d.register_executor(a["id"], lambda ctx: {"deployed": True})
    danger = d.submit_task("Engineering", "deploy release", required_capabilities=["deploy"])
    assert danger["status"] == TaskStatus.REQUIRES_APPROVAL and danger["risk"] == Risk.HIGH
    assert any(e["type"] == MultiAgentEvents.APPROVAL_REQUIRED for e in bus.history())
    with pytest.raises(UnauthorizedError):
        d.approve_task("Engineering", danger["id"])           # approver değil
    approved = d.approve_task("owner", danger["id"])          # owner onaylar → atanır+yürür
    assert approved["status"] == TaskStatus.COMPLETED and approved["approved_by"] == "owner"
    assert any(e["type"] == MultiAgentEvents.APPROVED for e in bus.history())


# ---- INTEGRATION: eligible_agents + stats + contract ----
def test_eligible_stats_contract(ma):
    d, _r, _b = ma
    d.register_agent("owner", "a1", capabilities=["a", "b"], trust=0.6)
    d.register_agent("owner", "a2", capabilities=["a"], trust=0.9, status=AgentStatus.PAUSED)
    elig = d.eligible_agents("owner", ["a"])
    assert len(elig) == 1 and elig[0]["name"] == "a1"         # paused olan elenir
    d.submit_task("owner", "transfer funds", required_capabilities=["a"])  # high → requires_approval
    s = d.stats()
    assert s["agents"] == 2 and s["pending_approval"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "multi_agent" and "approve_task" in c["operations"]


# ---- SMOKE: boot() → deterministik atama + Madde 24 uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    a = mio.multi_agent.register_agent("owner", "SahaAjanı", capabilities=["research"], trust=0.7)
    # executor yok → dürüst no_connector
    t = mio.multi_agent.submit_task("owner", "market taraması", required_capabilities=["research"])
    assert t["status"] == TaskStatus.NO_CONNECTOR and t["assigned_agent"] == a["id"]
    # yüksek-risk görev onaysız çalışmaz (Madde 24)
    danger = mio.multi_agent.submit_task("owner", "publish report", required_capabilities=["research"])
    assert danger["status"] == TaskStatus.REQUIRES_APPROVAL
    assert mio.multi_agent.contract()["version"] == "1.0.0"
    mio.close()
