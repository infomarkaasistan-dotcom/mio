"""MIO Core · Distributed Execution Domain (Faz 5 · Domain 40) — üretim testleri: unit+integration+smoke.

Anayasa özü: **Execution tek başına karar vermez; dağıtım DETERMİNİSTİK; yüksek-risk iş ONAY ister (Madde 24).**
Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik executor üzerinden. Deterministik zamanlama,
node sağlık/kapasite, idempotency (effectively-once), DÜRÜST no_node & no_connector, Madde 24, events doğrulanır."""

import pytest

from mio_core.domains.distributed_execution import (
    DistExecRepository,
    DistExecEvents,
    DistributedExecutionDomain,
    JobStatus,
    NodeStatus,
    NotFoundError,
    Risk,
    UnauthorizedError,
    ValidationError,
    classify_risk,
)
from mio_core.events import EventBus


def _build():
    repo = DistExecRepository(":memory:")
    bus = EventBus(record=True)
    dom = DistributedExecutionDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def dx():
    return _build()


# ---- UNIT: risk + validation + authz ----
def test_risk_validation_authz(dx):
    d, _r, _b = dx
    assert classify_risk("compute stats") == Risk.LOW
    assert classify_risk("migrate database") == Risk.HIGH     # tehlikeli işaret
    assert classify_risk("x", declared=Risk.HIGH) == Risk.HIGH
    with pytest.raises(UnauthorizedError):
        d.register_node("Perception", "n1")                   # reader ama writer değil
    with pytest.raises(ValidationError):
        d.register_node("owner", "n1", capacity=0)
    with pytest.raises(ValidationError):
        d.register_node("owner", "n1", status="uydurma")


# ---- INTEGRATION: DETERMİNİSTİK zamanlama (en boş düğüm kazanır) ----
def test_deterministic_scheduling_least_loaded(dx):
    d, _r, bus = dx
    big = d.register_node("owner", "big", capabilities=["cpu"], capacity=3)
    small = d.register_node("owner", "small", capabilities=["cpu"], capacity=1)
    d.register_executor(big["id"], lambda ctx: {"by": "big"})
    d.register_executor(small["id"], lambda ctx: {"by": "small"})
    j = d.submit("owner", "job1", required_capabilities=["cpu"])
    assert j["status"] == JobStatus.COMPLETED and j["assigned_node"] == big["id"]  # spare 3 > 1
    assert any(e["type"] == DistExecEvents.JOB_SCHEDULED for e in bus.history())


# ---- INTEGRATION: yetenek eşleşmesi + node sağlık (draining/down alınmaz) ----
def test_capability_and_health(dx):
    d, _r, _b = dx
    n = d.register_node("owner", "gpu-node", capabilities=["gpu"], capacity=1)
    d.register_executor(n["id"], lambda ctx: {"ok": True})
    # gerekli yetenek yok → no_node
    assert d.submit("owner", "need cpu", required_capabilities=["cpu"])["status"] == JobStatus.NO_NODE
    # düğüm draining → iş alamaz → no_node
    d.set_node_status("owner", n["id"], NodeStatus.DRAINING)
    assert d.submit("owner", "gpu job", required_capabilities=["gpu"])["status"] == JobStatus.NO_NODE
    # tekrar healthy → çalışır
    d.set_node_status("owner", n["id"], NodeStatus.HEALTHY)
    assert d.submit("owner", "gpu job2", required_capabilities=["gpu"])["status"] == JobStatus.COMPLETED


# ---- INTEGRATION: idempotency (effectively-once) ----
def test_idempotency_effectively_once(dx):
    d, _r, bus = dx
    n = d.register_node("owner", "n", capabilities=["x"])
    d.register_executor(n["id"], lambda ctx: {"ran": True})
    a = d.submit("owner", "do x", required_capabilities=["x"], idempotency_key="k-1")
    assert a["status"] == JobStatus.COMPLETED
    # aynı anahtar → yeni iş yaratılmaz, mevcut döner (dedup)
    b = d.submit("owner", "do x again", required_capabilities=["x"], idempotency_key="k-1")
    assert b["id"] == a["id"]
    assert any(e["type"] == DistExecEvents.JOB_DEDUPED for e in bus.history())
    assert d.stats()["jobs"] == 1 and d.stats()["deduped"] == 1


# ---- INTEGRATION: node atandı ama executor yok → DÜRÜST no_connector ----
def test_no_connector_when_no_executor(dx):
    d, _r, bus = dx
    n = d.register_node("owner", "n", capabilities=["build"])
    job = d.submit("owner", "build", required_capabilities=["build"])
    assert job["status"] == JobStatus.NO_CONNECTOR and job["assigned_node"] == n["id"]
    assert any(e["type"] == DistExecEvents.NO_CONNECTOR for e in bus.history())


# ---- INTEGRATION: executor hatası → failed ----
def test_executor_failure(dx):
    d, _r, _b = dx
    n = d.register_node("owner", "n", capabilities=["x"])
    d.register_executor(n["id"], lambda ctx: (_ for _ in ()).throw(RuntimeError("node paniği")))
    job = d.submit("owner", "do x", required_capabilities=["x"])
    assert job["status"] == JobStatus.FAILED and "node paniği" in job["error"]


# ---- INTEGRATION: yüksek-risk iş → requires_approval (Madde 24) ----
def test_high_risk_requires_approval(dx):
    d, _r, bus = dx
    n = d.register_node("owner", "db", capabilities=["db"])
    d.register_executor(n["id"], lambda ctx: {"migrated": True})
    danger = d.submit("Scheduler", "migrate shard", required_capabilities=["db"])
    assert danger["status"] == JobStatus.REQUIRES_APPROVAL and danger["risk"] == Risk.HIGH
    assert any(e["type"] == DistExecEvents.APPROVAL_REQUIRED for e in bus.history())
    with pytest.raises(UnauthorizedError):
        d.approve_job("Scheduler", danger["id"])              # approver değil
    approved = d.approve_job("owner", danger["id"])
    assert approved["status"] == JobStatus.COMPLETED and approved["approved_by"] == "owner"
    assert any(e["type"] == DistExecEvents.APPROVED for e in bus.history())


# ---- INTEGRATION: eligible_nodes + stats + contract ----
def test_eligible_stats_contract(dx):
    d, _r, _b = dx
    d.register_node("owner", "a", capabilities=["x", "y"], capacity=2)
    d.register_node("owner", "b", capabilities=["x"], status=NodeStatus.DOWN)
    elig = d.eligible_nodes("owner", ["x"])
    assert len(elig) == 1 and elig[0]["name"] == "a"          # down olan elenir
    d.submit("owner", "drop table", required_capabilities=["x"])  # high → requires_approval
    s = d.stats()
    assert s["nodes"] == 2 and s["pending_approval"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "distributed_execution" and "approve_job" in c["operations"]
    with pytest.raises(NotFoundError):
        d.get_job("owner", "yok")


# ---- SMOKE: boot() → deterministik dağıtım + Madde 24 uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    dxe = mio.distributed_execution
    n = dxe.register_node("owner", "worker-1", capabilities=["etl"], capacity=2)
    # executor yok → dürüst no_connector
    j = dxe.submit("owner", "etl batch", required_capabilities=["etl"], idempotency_key="etl-42")
    assert j["status"] == JobStatus.NO_CONNECTOR and j["assigned_node"] == n["id"]
    # yüksek-risk iş onaysız çalışmaz (Madde 24)
    danger = dxe.submit("owner", "purge old data", required_capabilities=["etl"])
    assert danger["status"] == JobStatus.REQUIRES_APPROVAL
    assert dxe.contract()["version"] == "1.0.0"
    mio.close()
