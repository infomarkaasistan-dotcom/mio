"""MIO Core · Native Adapter Layer — MCP-olmayan yerel yetenekler Capability olarak (üretim testleri)."""

from mio_core.adapters.native import (
    ReasoningExecutor,
    ShellExecutor,
    reasoning_capability,
    register_native,
    shell_capability,
)
from mio_core.capability import CapabilityRegistry
from mio_core.execution import ToolOrchestrator, ToolRequest


def test_reasoning_native_capability():
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    register_native(orch, reg, reasoning_capability(), ReasoningExecutor())
    res = orch.execute(ToolRequest("reasoning.calc", "calc", {"expr": "2+3*4"}, requester="Finance"))
    assert res.success and res.output == 14                 # native, deterministik, orchestrator üzerinden
    # güvensiz ifade → başarısız (eval yok)
    bad = orch.execute(ToolRequest("reasoning.calc", "calc", {"expr": "__import__('os')"}))
    assert not bad.success


def test_shell_native_is_approval_gated():
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    register_native(orch, reg, shell_capability(), ShellExecutor())
    # yüksek risk + requires_user_approval → onaysız BLOKE (gerçek shell çalıştırılmaz)
    res = orch.execute(ToolRequest("system.shell", "run", {"command": "echo x"},
                                   requester="Engineering"))
    assert res.blocked and res.verdict == "await_approval"
    # Finance kullanamaz (usable_by)
    res2 = orch.execute(ToolRequest("system.shell", "run", {"command": "echo x"},
                                    requester="Finance", user_approved=True))
    assert res2.blocked and "kullanamaz" in res2.reason
