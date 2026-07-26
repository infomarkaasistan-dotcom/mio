"""MIO Core · Reasoning Capability Suite — deterministik karar-destek (Native Adapter), LLM-BAĞIMSIZ.

Executive'in/Brain'lerin karar kalitesini LLM'e gerek kalmadan artıran araçlar (AI Independence §9: zekâ
modellerde değil Executive/Capability katmanında). Tool Orchestrator üzerinden çağrılır; çekirdek büyümez.

Eylemler:
  - rank:  ağırlıklı çok-kriterli sıralama.
  - compare: en iyi seçeneği döner (rank tepesi).
  - constraint_check: bir adayın kısıtları karşılayıp karşılamadığı.
  - score: tek bir öğe için ağırlıklı skor."""

from __future__ import annotations

import operator
from typing import Any

from mio_core.capability import Capability, CapabilityRegistry, RiskLevel

__all__ = ["ReasoningSuite", "reasoning_suite_capability", "register_reasoning"]

_OPS = {"==": operator.eq, "!=": operator.ne, ">": operator.gt, ">=": operator.ge,
        "<": operator.lt, "<=": operator.le, "in": lambda a, b: a in b, "not_in": lambda a, b: a not in b}


def _weighted(item: dict, weights: dict) -> float:
    scores = item.get("scores", {}) if isinstance(item, dict) else {}
    keys = weights or scores
    return round(sum(float(weights.get(k, 1)) * float(scores.get(k, 0)) for k in keys), 4)


class ReasoningSuite:
    def execute(self, capability: Capability, action: str, args: dict[str, Any]) -> Any:
        items = args.get("items", [])
        weights = args.get("weights", {})
        if action in ("rank", "compare"):
            ranked = sorted(
                ({"name": it.get("name"), "score": _weighted(it, weights)} for it in items),
                key=lambda r: r["score"], reverse=True)
            return ranked if action == "rank" else (ranked[0] if ranked else None)
        if action == "score":
            return _weighted(args.get("item", {}), weights)
        if action == "constraint_check":
            candidate = args.get("candidate", {})
            failures = []
            for c in args.get("constraints", []):
                field, op, val = c.get("field"), c.get("op"), c.get("value")
                fn = _OPS.get(op)
                if fn is None:
                    failures.append({"field": field, "reason": f"bilinmeyen op: {op}"})
                    continue
                if not fn(candidate.get(field), val):
                    failures.append({"field": field, "op": op, "expected": val,
                                     "actual": candidate.get(field)})
            return {"passed": not failures, "failures": failures}
        raise ValueError(f"desteklenmeyen eylem: {action}")


def reasoning_suite_capability() -> Capability:
    return Capability(
        "reasoning.suite", "Deterministik karar-destek (rank/compare/constraint/score)",
        category="reasoning", can_do=["rank", "compare", "constraint_check", "score"],
        risk_level=RiskLevel.LOW, source="native")


def register_reasoning(orchestrator, capabilities: CapabilityRegistry) -> Capability:
    cap = reasoning_suite_capability()
    capabilities.register(cap)
    orchestrator.register_executor(cap.name, ReasoningSuite())
    return cap
