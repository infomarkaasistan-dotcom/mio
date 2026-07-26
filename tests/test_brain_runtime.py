"""MIO Core · Domain Brain yürütme — üretim testleri (deterministik; LLM opsiyonel adaptör)."""

import pytest

from mio_core.brain_runtime import DomainBrainRuntime
from mio_core.brains import BrainRegistry, default_domain_brains
from mio_core.capability import Capability, CapabilityRegistry
from mio_core.execution import ModelGateway, ToolOrchestrator, llm_capability
from mio_core.execution.model_gateway import ModelSpec
from mio_core.knowledge import KnowledgeBase, default_innate_knowledge


class OkExecutor:
    def execute(self, cap, action, args):
        return "done"


class FakeLLM:
    def generate(self, model, prompt, system, max_tokens):
        assert "KARAR VERMEZSİN" in system                # Brain'e "karar verme" talimatı gidiyor
        return "Yaklaşım: ücretsiz kanallarla içerik üret."


def _brains():
    b = BrainRegistry()
    b.register_all(default_domain_brains())
    return b


def _kb():
    k = KnowledgeBase()
    k.add_all(default_innate_knowledge())
    return k


def test_perform_uses_innate_knowledge_and_capabilities():
    caps = CapabilityRegistry()
    caps.register(Capability("filesystem", connected=True))                    # ["*"]
    caps.register(Capability("code_execution", usable_by_brains=["Engineering", "Executive"], connected=True))
    rt = DomainBrainRuntime(_brains(), caps, _kb(), ToolOrchestrator(caps), consult_llm=False)
    r = rt.perform("Engineering", "tekrarlayan raporu otomatikleştir", context_tags={"repetitive_task"})
    assert r.known
    assert any("otomasyon" in rec["recommendation"].lower() for rec in r.recommendations)  # innate bilgi
    assert set(r.available_capabilities) == {"filesystem", "code_execution"}
    assert r.advisory is None                                                   # LLM yok


def test_capabilities_filtered_by_brain():
    caps = CapabilityRegistry()
    caps.register(Capability("filesystem", connected=True))
    caps.register(Capability("code_execution", usable_by_brains=["Engineering", "Executive"], connected=True))
    rt = DomainBrainRuntime(_brains(), caps, _kb(), ToolOrchestrator(caps), consult_llm=False)
    fin = rt.perform("Finance", "bütçe planla")
    assert "filesystem" in fin.available_capabilities
    assert "code_execution" not in fin.available_capabilities                  # Finance kullanamaz


def test_unknown_brain():
    rt = DomainBrainRuntime(_brains(), CapabilityRegistry(), _kb(), ToolOrchestrator(CapabilityRegistry()))
    r = rt.perform("Nope", "x")
    assert not r.known and r.error


def test_act_routes_through_orchestrator_and_respects_permissions():
    caps = CapabilityRegistry()
    caps.register(Capability("filesystem"))                                    # ["*"]
    caps.register(Capability("code_execution", usable_by_brains=["Engineering", "Executive"]))
    orch = ToolOrchestrator(caps)
    orch.register_executor("filesystem", OkExecutor())                         # connect
    orch.register_executor("code_execution", OkExecutor())
    rt = DomainBrainRuntime(_brains(), caps, _kb(), orch, consult_llm=False)
    ok = rt.act("Marketing", "filesystem", "read", {"path": "x"})
    assert ok.success and ok.output == "done"
    blocked = rt.act("Marketing", "code_execution", "run", {})                 # Marketing yetkisiz
    assert blocked.blocked and "kullanamaz" in blocked.reason


def test_llm_advisory_via_orchestrator():
    caps = CapabilityRegistry()
    caps.register(llm_capability())
    orch = ToolOrchestrator(caps)
    gw = ModelGateway()
    gw.register_model(ModelSpec("m", "ollama", local=True), FakeLLM())
    orch.register_executor("llm", gw)                                          # "llm" bağlı
    rt = DomainBrainRuntime(_brains(), caps, _kb(), orch, consult_llm=True)
    r = rt.perform("Marketing", "büyüme planı")
    assert r.advisory and "içerik" in r.advisory                              # LLM danışman öneri verdi
    assert r.advisor_model == "m"
