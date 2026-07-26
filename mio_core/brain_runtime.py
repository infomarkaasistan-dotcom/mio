"""MIO Core · Domain Brain yürütme (ADR-0002 Madde 2), çekirdek LLM-BAĞIMSIZ.

Bir Domain Brain (Finance/Marketing/Engineering...) alanındaki bir görevi NASIL ele alacağını üretir:
  - INNATE BİLGİ (deterministik): `KnowledgeBase.apply(context)` → alanına uygun kural/heuristik/öneriler.
  - ERİŞEBİLDİĞİ CAPABILITY'ler: `CapabilityRegistry.list_for_brain(brain)` → yalnız bu Brain'in ve BAĞLI.
  - OPSİYONEL LLM-DANIŞMAN: Tool Orchestrator üzerinden "llm" (bağlıysa) → yaklaşım ÖNERİSİ (karar değil).

İki değişmez: Brain **KARAR VERMEZ** (Executive verir) ve **doğrudan API çağırmaz** — her eylem
`act()` ile Tool Orchestrator'dan geçer (izin/onay/governance/audit). LLM yoksa Brain innate bilgiyle
çalışmaya devam eder (dürüst, LLM-siz).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from mio_core.brains import BrainRegistry
from mio_core.capability import CapabilityRegistry
from mio_core.execution import ToolOrchestrator, ToolRequest, ToolResult
from mio_core.knowledge import KnowledgeBase

__all__ = ["BrainResult", "DomainBrainRuntime"]


@dataclass
class BrainResult:
    brain: str
    task: str
    known: bool = True
    knowledge_domains: list[str] = field(default_factory=list)
    available_capabilities: list[str] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)  # innate bilgi → deterministik öneri
    advisory: Optional[str] = None                                       # LLM-danışman (varsa) — öneri, karar değil
    advisor_model: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"brain": self.brain, "task": self.task, "known": self.known,
                "knowledge_domains": list(self.knowledge_domains),
                "available_capabilities": list(self.available_capabilities),
                "recommendations": list(self.recommendations), "advisory": self.advisory,
                "advisor_model": self.advisor_model, "error": self.error}


class DomainBrainRuntime:
    """14 Domain Brain'in yürütme motoru. Brain'i alanında uzman bir YÜRÜTÜCÜ yapar; karar-verici değil."""

    def __init__(self, brains: BrainRegistry, capabilities: CapabilityRegistry,
                 knowledge: KnowledgeBase, orchestrator: ToolOrchestrator, *,
                 consult_llm: bool = True) -> None:
        self._brains = brains
        self._caps = capabilities
        self._knowledge = knowledge
        self._orch = orchestrator
        self._consult_llm = consult_llm

    def perform(self, brain_name: str, task: str, *,
                context_tags: Optional[set[str]] = None) -> BrainResult:
        """Brain'in bir görevi alanında nasıl ele alacağını üretir (innate bilgi + capability + LLM-danışman).
        HİÇBİR ŞEY YÜRÜTMEZ — yaklaşım üretir. Yürütme, Executive kararıyla `act()` üzerinden olur."""
        brain = self._brains.get(brain_name)
        if brain is None:
            return BrainResult(brain=brain_name, task=task, known=False,
                               error=f"Bilinmeyen Brain: {brain_name}")
        recs = self._knowledge.apply(set(context_tags or set()))
        caps = self._caps.list_for_brain(brain_name, only_connected=True)
        advisory, model = (None, None)
        if self._consult_llm:
            advisory, model = self._advise(brain.name, brain.knowledge_domains, task, recs, caps)
        return BrainResult(
            brain=brain.name, task=task, known=True,
            knowledge_domains=list(brain.knowledge_domains),
            available_capabilities=[c.name for c in caps],
            recommendations=[{"name": a.name, "recommendation": a.recommendation,
                              "confidence": a.confidence, "type": a.ktype} for a in recs],
            advisory=advisory, advisor_model=model,
        )

    def act(self, brain_name: str, capability: str, action: str,
            args: Optional[dict[str, Any]] = None, **kwargs: Any) -> ToolResult:
        """Brain bir aracı KULLANIR — YALNIZ Tool Orchestrator üzerinden (brain=requester). İzin/onay/
        governance/audit otomatik uygulanır. Brain doğrudan API çağıramaz."""
        return self._orch.execute(ToolRequest(
            capability=capability, action=action, args=args or {}, requester=brain_name, **kwargs))

    # -- LLM danışman (Tool Orchestrator üzerinden; karar değil, öneri) ----- #
    def _advise(self, brain_name: str, domains: list[str], task: str, recs, caps) -> tuple:
        cap_names = ", ".join(c.name for c in caps) or "(bağlı araç yok)"
        rec_lines = "; ".join(f"{a.name}: {a.recommendation}" for a in recs) or "(uygulanabilir kural yok)"
        system = (f"Sen MIO'nun {brain_name} Brain'isin. Uzmanlık alanların: {', '.join(domains)}. "
                  "KARAR VERMEZSİN (kararı Executive verir); yalnız alanında NASIL yapılacağına dair kısa, "
                  "uygulanabilir bir ÖNERİ sunarsın. Sahip olmadığın araçları önerme; 'bağlı değil'i dürüstçe belirt.")
        prompt = (f"Görev: {task}\nErişebildiğin araçlar: {cap_names}\n"
                  f"İlgili innate kurallar: {rec_lines}\n"
                  "Bu görevi alanında nasıl ele alırsın? Somut, uygulanabilir bir yaklaşım öner.")
        res = self._orch.execute(ToolRequest(
            "llm", "generate", {"prompt": prompt, "system": system, "max_tokens": 300},
            requester=brain_name))
        if res.success and isinstance(res.output, dict):
            return res.output.get("text"), res.output.get("model")
        return None, None
