"""MIO Core · Tool Orchestrator — üretim testleri (deterministik, LLM-siz).

Capability selection + izin/onay + E4 governance + retry + fallback + audit. "Hiçbir Brain doğrudan API
kullanmaz" ilkesinin motoru. Executor'lar GERÇEK adaptör test double'larıdır (sistemde mock yok).
"""

import pytest

from mio_core.capability import Capability, CapabilityRegistry, RiskLevel
from mio_core.execution import SQLiteToolAuditStore, ToolOrchestrator, ToolRequest
from mio_core.executive import ExecutiveState, GovernanceEngine, SQLiteExecutiveStateStore


class OkExecutor:
    def __init__(self, output="done"):
        self.output = output

    def execute(self, cap, action, args):
        return self.output


class FailExecutor:
    def execute(self, cap, action, args):
        raise RuntimeError("boom")


class FlakyExecutor:
    def __init__(self, fail_times=1):
        self.fail_times = fail_times
        self.calls = 0

    def execute(self, cap, action, args):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("flaky")
        return "recovered"


def _reg(*caps):
    r = CapabilityRegistry()
    for c in caps:
        r.register(c)
    return r


# ---- Temel yürütme + audit ----
def test_success_and_audit():
    reg = _reg(Capability("filesystem"))
    audit = SQLiteToolAuditStore(":memory:")
    orch = ToolOrchestrator(reg, audit_store=audit)
    orch.register_executor("filesystem", OkExecutor("content"))
    res = orch.execute(ToolRequest("filesystem", "read", {"path": "x"}))
    assert res.success and res.output == "content" and res.attempts == 1
    entries = audit.list()
    assert entries[0].capability == "filesystem" and entries[0].success
    audit.close()


# ---- Dürüst engeller ----
def test_unknown_capability_blocked():
    res = ToolOrchestrator(CapabilityRegistry()).execute(ToolRequest("nope", "x"))
    assert res.blocked and "kayıtlı değil" in res.reason


def test_not_connected_blocked():
    orch = ToolOrchestrator(_reg(Capability("x")))       # executor yok → connected değil
    res = orch.execute(ToolRequest("x", "a"))
    assert res.blocked and "bağlı değil" in res.reason


def test_usable_by_brain_blocked():
    reg = _reg(Capability("git", usable_by_brains=["Engineering"]))
    orch = ToolOrchestrator(reg)
    orch.register_executor("git", OkExecutor())
    res = orch.execute(ToolRequest("git", "commit", requester="Finance"))
    assert res.blocked and "kullanamaz" in res.reason


def test_no_executor_blocked():
    reg = _reg(Capability("x", connected=True))           # bağlı ama yürütücü yok
    res = ToolOrchestrator(reg).execute(ToolRequest("x", "a"))
    assert res.blocked and "yürütücü yok" in res.reason


# ---- Kullanıcı onay kapısı (Financial Rule) ----
def test_user_approval_gate():
    reg = _reg(Capability("payment", requires_user_approval=True))
    orch = ToolOrchestrator(reg)
    orch.register_executor("payment", OkExecutor("paid"))
    res = orch.execute(ToolRequest("payment", "pay", requester="Finance"))
    assert res.blocked and res.verdict == "await_approval"
    res2 = orch.execute(ToolRequest("payment", "pay", requester="Finance", user_approved=True))
    assert res2.success and res2.output == "paid"


# ---- Executive Governance (E4) entegrasyonu ----
def _gov_state():
    st = ExecutiveState(SQLiteExecutiveStateStore(":memory:"))
    st.ensure_identity("MIO")
    return st, GovernanceEngine(st)


def test_high_risk_routes_governance_and_rejects_misaligned():
    st, gov = _gov_state()
    reg = _reg(Capability("code_execution", risk_level=RiskLevel.HIGH))
    orch = ToolOrchestrator(reg, governance=gov)
    orch.register_executor("code_execution", OkExecutor())
    res = orch.execute(ToolRequest("code_execution", "run", goal_id="gX"))  # gX aktif değil → REJECT
    assert res.blocked and res.verdict == "reject"


def test_high_risk_governance_approves_aligned():
    st, gov = _gov_state()
    st.track_goal("g1")
    reg = _reg(Capability("code_execution", risk_level=RiskLevel.HIGH))
    orch = ToolOrchestrator(reg, governance=gov)
    orch.register_executor("code_execution", OkExecutor("ran"))
    res = orch.execute(ToolRequest("code_execution", "run", goal_id="g1"))
    assert res.success and res.output == "ran"


# ---- Retry + Fallback ----
def test_retry_recovers():
    reg = _reg(Capability("x"))
    orch = ToolOrchestrator(reg, default_retries=2)
    orch.register_executor("x", FlakyExecutor(fail_times=1))
    res = orch.execute(ToolRequest("x", "a"))
    assert res.success and res.output == "recovered" and res.attempts == 2


def test_fallback_to_alternative():
    reg = _reg(Capability("primary", alternatives=["backup"]), Capability("backup"))
    orch = ToolOrchestrator(reg, default_retries=1)
    orch.register_executor("primary", FailExecutor())
    orch.register_executor("backup", OkExecutor("via-backup"))
    res = orch.execute(ToolRequest("primary", "a"))
    assert res.success and res.fallback_used == "backup" and res.output == "via-backup"


def test_retry_exhausted_failure():
    reg = _reg(Capability("x"))                            # alternatif yok
    orch = ToolOrchestrator(reg, default_retries=1)
    orch.register_executor("x", FailExecutor())
    res = orch.execute(ToolRequest("x", "a"))
    assert not res.success and not res.blocked and res.attempts == 2 and "boom" in res.error


def test_audit_records_blocked_too():
    audit = SQLiteToolAuditStore(":memory:")
    orch = ToolOrchestrator(CapabilityRegistry(), audit_store=audit)
    orch.execute(ToolRequest("nope", "x"))
    assert audit.list()[0].blocked is True
    audit.close()
