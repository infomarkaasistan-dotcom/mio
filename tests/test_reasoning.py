"""MIO Core · Reasoning Capability Suite — deterministik karar-destek (üretim testleri, LLM-siz)."""

from mio_core.adapters.reasoning import ReasoningSuite, register_reasoning
from mio_core.capability import CapabilityRegistry
from mio_core.execution import ToolOrchestrator, ToolRequest


def _orch():
    reg = CapabilityRegistry()
    orch = ToolOrchestrator(reg)
    register_reasoning(orch, reg)
    return reg, orch


def test_rank_and_compare():
    _reg, orch = _orch()
    items = [{"name": "A", "scores": {"trust": 0.9, "cost": 0.2}},
             {"name": "B", "scores": {"trust": 0.5, "cost": 0.9}}]
    weights = {"trust": 2.0, "cost": -1.0}
    ranked = orch.execute(ToolRequest("reasoning.suite", "rank", {"items": items, "weights": weights})).output
    assert [r["name"] for r in ranked] == ["A", "B"]           # A: 1.8-0.2=1.6 > B: 1.0-0.9=0.1
    best = orch.execute(ToolRequest("reasoning.suite", "compare", {"items": items, "weights": weights})).output
    assert best["name"] == "A"


def test_constraint_check():
    _reg, orch = _orch()
    res = orch.execute(ToolRequest("reasoning.suite", "constraint_check", {
        "candidate": {"budget": 0, "risk": "high"},
        "constraints": [{"field": "budget", "op": ">", "value": 0},
                        {"field": "risk", "op": "in", "value": ["low", "medium"]}]})).output
    assert res["passed"] is False and len(res["failures"]) == 2


def test_born_with_reasoning(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    assert mio.capabilities.can("reasoning.suite")             # doğuştan native reasoning
    res = mio.orchestrator.execute(ToolRequest("reasoning.suite", "score",
                                               {"item": {"scores": {"x": 3}}, "weights": {"x": 2}},
                                               requester="Executive"))
    assert res.success and res.output == 6.0
    mio.close()
