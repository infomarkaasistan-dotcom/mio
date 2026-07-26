"""MIO Core · Workflow Domain (yol haritası K1) — DAG + checkpoint/resume + human-approval + rollback.

Deterministik: döngü/eksik-bağımlılık reddi, topolojik sıra, ready hesabı, checkpoint, human-approval (Madde 24),
rollback (descendant), Executive köprüsü (workflow_run), katman ayrımı (domain connector çağırmaz)."""

import pytest

from mio_core.domains.workflow import (
    DAGError,
    TaskStatus,
    ValidationError,
    UnauthorizedError,
    WorkflowDomain,
    WorkflowEvents,
    WorkflowRepository,
    WorkflowStatus,
    topological_order,
    validate_dag,
)
from mio_core.domains.workflow.models import WorkflowTask
from mio_core.events import EventBus


def _build():
    repo = WorkflowRepository(":memory:")
    bus = EventBus(record=True)
    return WorkflowDomain(repo, bus=bus), repo, bus


@pytest.fixture
def wd():
    return _build()


# ---- UNIT: DAG doğrulama + topolojik sıra ----
def test_validate_dag_and_topo():
    tasks = [WorkflowTask(name="a"), WorkflowTask(name="b", depends_on=["a"]),
             WorkflowTask(name="c", depends_on=["a"]), WorkflowTask(name="d", depends_on=["b", "c"])]
    validate_dag(tasks)                               # geçerli DAG
    assert topological_order(tasks) == ["a", "b", "c", "d"]   # deterministik
    # döngü
    with pytest.raises(DAGError):
        validate_dag([WorkflowTask(name="x", depends_on=["y"]), WorkflowTask(name="y", depends_on=["x"])])
    # eksik bağımlılık
    with pytest.raises(DAGError):
        validate_dag([WorkflowTask(name="a", depends_on=["yok"])])


def test_create_validation(wd):
    d, _r, _b = wd
    with pytest.raises(UnauthorizedError):
        d.create_workflow("Reasoning", "x", [{"name": "a"}])
    with pytest.raises(ValidationError):
        d.create_workflow("owner", "x", [])           # boş
    with pytest.raises(DAGError):
        d.create_workflow("owner", "cyclic", [{"name": "a", "depends_on": ["b"]},
                                              {"name": "b", "depends_on": ["a"]}])


# ---- ready hesabı + checkpoint ----
def test_ready_and_checkpoint(wd):
    d, _r, bus = wd
    wf = d.create_workflow("owner", "P", [{"name": "a"}, {"name": "b", "depends_on": ["a"]}])
    wid = wf["id"]
    d.start("owner", wid)
    ready = d.ready_tasks("owner", wid)
    assert [t["name"] for t in ready] == ["a"]        # yalnız a hazır (b bekliyor)
    a_id = next(t["id"] for t in wf["tasks"] if t["name"] == "a")
    d.complete_task("owner", wid, a_id)
    ready2 = d.ready_tasks("owner", wid)
    assert [t["name"] for t in ready2] == ["b"]       # a tamamlanınca b hazır (checkpoint)
    assert any(e["type"] == WorkflowEvents.TASK_COMPLETED for e in bus.history())


# ---- human-approval (Madde 24) ----
def test_human_approval_gate(wd):
    d, _r, bus = wd
    wf = d.create_workflow("owner", "P", [{"name": "a", "requires_approval": True}])
    wid, a_id = wf["id"], wf["tasks"][0]["id"]
    d.start("owner", wid)
    ready = d.ready_tasks("owner", wid)
    assert ready == []                                # onay bekliyor → ready değil
    got = d.get_workflow("owner", wid)
    assert got["tasks"][0]["status"] == TaskStatus.BLOCKED_APPROVAL
    assert any(e["type"] == WorkflowEvents.APPROVAL_REQUIRED for e in bus.history())
    with pytest.raises(UnauthorizedError):
        d.approve_task("Engineering", wid, a_id)      # approver değil
    d.approve_task("owner", wid, a_id)
    assert [t["name"] for t in d.ready_tasks("owner", wid)] == ["a"]   # onaydan sonra ready


# ---- rollback (descendant) ----
def test_rollback_descendants(wd):
    d, _r, _b = wd
    wf = d.create_workflow("owner", "P", [{"name": "a"}, {"name": "b", "depends_on": ["a"]},
                                          {"name": "c", "depends_on": ["b"]}])
    wid = wf["id"]
    d.start("owner", wid)
    ids = {t["name"]: t["id"] for t in wf["tasks"]}
    d.complete_task("owner", wid, ids["a"])
    d.complete_task("owner", wid, ids["b"])
    # b'yi rollback → b ve ardılı c pending; a etkilenmez
    rb = d.rollback("owner", wid, ids["b"])
    st = {t["name"]: t["status"] for t in rb["tasks"]}
    assert st["a"] == TaskStatus.COMPLETED and st["b"] in (TaskStatus.READY, TaskStatus.PENDING)
    assert st["c"] == TaskStatus.PENDING


# ---- KATMAN AYRIMI: domain connector import etmez ----
def test_domain_no_connector_import():
    import ast
    from pathlib import Path
    pkg = Path(__file__).resolve().parent.parent / "mio_core" / "domains" / "workflow"
    for py in pkg.glob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            mod = (node.module if isinstance(node, ast.ImportFrom) else None) or ""
            assert "mio_core.connectors" not in mod


# ---- stats + contract ----
def test_stats_contract(wd):
    d, _r, _b = wd
    d.create_workflow("owner", "P", [{"name": "a"}])
    st = d.stats()
    assert st["workflows"] == 1 and st["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "workflow" and "rollback" in c["operations"]


# ---- EXECUTIVE KÖPRÜSÜ: workflow_run DAG'ı yürütür (checkpoint + resume + approval) ----
def test_executive_bridge_run(tmp_path):
    from mio_core.runtime import boot
    from mio_core import appservice
    from mio_core.connectors import CallableConnector, ConnectorCategory, Cap
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        # a (salt-mantık) → b (capability, human-approval) → c
        wf = appservice.workflow_create(mio, "Pipe", [
            {"name": "a"},
            {"name": "b", "depends_on": ["a"], "capability": "fs.read",
             "request": {"path": "x"}, "requires_approval": True},
            {"name": "c", "depends_on": ["b"]}])
        wid = wf["id"]
        # fs connector bağla (Executive tarafı)
        mio.connectors.register(CallableConnector("fs", ConnectorCategory.SYSTEM,
                                                  handlers={Cap.FS_READ: lambda r: {"data": "ok"}}))
        # onaysız run → a tamamlanır, b onay bekler → durur (resume mümkün)
        r0 = appservice.workflow_run(mio, wid)
        assert r0["status"] == "running" and r0["progress"] < 1.0
        # onaylı run → b (fs.read executed) + c tamamlanır → completed
        r1 = appservice.workflow_run(mio, wid, approve=True)
        assert r1["status"] == "completed" and r1["progress"] == 1.0
    finally:
        mio.close()
