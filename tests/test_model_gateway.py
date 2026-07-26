"""MIO Core · X4 Model Gateway — üretim testleri (deterministik, çekirdek LLM-siz çalışır).

Routing + failover + LLM'in Tool Orchestrator üzerinden bir ARAÇ olarak kullanılması. Sağlayıcılar
GERÇEK adaptör test double'larıdır.
"""

import pytest

from mio_core.capability import CapabilityRegistry
from mio_core.execution import (
    GatewayError,
    ModelGateway,
    ModelSpec,
    SQLiteToolAuditStore,
    ToolOrchestrator,
    ToolRequest,
    llm_capability,
)


class FakeProvider:
    def __init__(self, reply="cevap", fail=False):
        self.reply = reply
        self.fail = fail
        self.calls = 0

    def generate(self, model, prompt, system, max_tokens):
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider down")
        return f"{self.reply}[{model.name}]"


def _two_model_gateway():
    gw = ModelGateway()
    gw.register_model(ModelSpec("small", "ollama", quality=0.5, local=True), FakeProvider("yerel"))
    gw.register_model(ModelSpec("big", "openai", quality=0.95, cost=0.01), FakeProvider("bulut"))
    return gw


# ---- Routing ----
def test_routing_quality_picks_best():
    r = _two_model_gateway().generate("selam", priority="quality")
    assert r.model == "big"


def test_routing_privacy_picks_local():
    r = _two_model_gateway().generate("selam", privacy=True)
    assert r.model == "small"                       # yalnız yerel


def test_failover_across_providers():
    gw = ModelGateway()
    gw.register_model(ModelSpec("a", "p1", quality=0.9), FakeProvider(fail=True))
    gw.register_model(ModelSpec("b", "p2", quality=0.5), FakeProvider("ok"))
    r = gw.generate("x", priority="quality")         # a (kalite) düşer → b
    assert r.model == "b" and r.attempts == 2


def test_no_models_is_honest_error():
    with pytest.raises(GatewayError):
        ModelGateway().generate("x")                 # sağlayıcı yok → dürüst hata (çekirdek yine çalışır)


# ---- ToolExecutor arayüzü ----
def test_execute_tool_interface():
    gw = _two_model_gateway()
    out = gw.execute(llm_capability(), "generate", {"prompt": "x", "priority": "quality"})
    assert out["model"] == "big" and out["text"].startswith("bulut")


def test_execute_rejects_unknown_action():
    with pytest.raises(ValueError):
        _two_model_gateway().execute(llm_capability(), "delete", {})


# ---- LLM YALNIZ Tool Orchestrator üzerinden (hiçbir Brain doğrudan çağırmaz) ----
def test_llm_used_only_via_orchestrator():
    reg = CapabilityRegistry()
    reg.register(llm_capability())
    audit = SQLiteToolAuditStore(":memory:")
    orch = ToolOrchestrator(reg, audit_store=audit)
    gw = ModelGateway()
    gw.register_model(ModelSpec("m", "ollama", local=True), FakeProvider("cevap"))
    orch.register_executor("llm", gw)                # "llm" yeteneği artık bağlı

    res = orch.execute(ToolRequest("llm", "generate", {"prompt": "merhaba"}, requester="Marketing"))
    assert res.success and "cevap" in res.output["text"]
    # audit: Marketing Brain'in LLM kullanımı kaydedildi (doğrudan API değil)
    assert audit.list()[0].capability == "llm" and audit.list()[0].requester == "Marketing"
    audit.close()
