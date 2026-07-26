"""MIO Core · Native Adapter Layer — MCP-olmayan yerel sistemler (Windows/reasoning/...) Capability olarak.

Executive için MCP ile native arasında FARK YOKTUR: her ikisi de Tool Orchestrator üzerinden, izin/onay/
governance/audit ile çalışır. Native yetenekler `register_native` ile eklenir — çekirdek büyümez, ekosistem
büyür. Örnekler: reasoning.calc (güvenli deterministik), system.shell (yüksek risk, kullanıcı onaylı).

Hiçbir Brain doğrudan sistem çağırmaz; native executor da orchestrator arkasındadır."""

from __future__ import annotations

import ast
import operator
import subprocess
from typing import Any

from mio_core.capability import Capability, CapabilityRegistry, RiskLevel

__all__ = ["ReasoningExecutor", "ShellExecutor", "reasoning_capability", "shell_capability",
           "register_native"]

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.FloorDiv: operator.floordiv}


def _safe_eval(node) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("izinsiz/güvensiz ifade")


class ReasoningExecutor:
    """Güvenli, deterministik yerel muhakeme (aritmetik). Sistem erişimi YOK — safe."""

    def execute(self, capability: Capability, action: str, args: dict[str, Any]) -> Any:
        if action == "calc":
            return _safe_eval(ast.parse(str(args.get("expr", "")), mode="eval"))
        raise ValueError(f"desteklenmeyen eylem: {action}")


class ShellExecutor:
    """Yerel kabuk (Windows PowerShell). YÜKSEK RİSK — capability requires_user_approval ile gated;
    orchestrator kullanıcı onayı olmadan yürütmez."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def execute(self, capability: Capability, action: str, args: dict[str, Any]) -> Any:
        cmd = str(args.get("command", "")).strip()
        if not cmd:
            raise ValueError("command gerekli")
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                              capture_output=True, text=True, timeout=args.get("timeout", self._timeout))
        return {"stdout": proc.stdout[-4000:], "stderr": proc.stderr[-1000:], "returncode": proc.returncode}


def reasoning_capability() -> Capability:
    return Capability("reasoning.calc", "Deterministik hesap/muhakeme (güvenli)", category="reasoning",
                      can_do=["calc"], risk_level=RiskLevel.LOW, source="native")


def shell_capability() -> Capability:
    return Capability("system.shell", "Yerel kabuk komutu (PowerShell)", category="system",
                      can_do=["run"], cannot_do=["onaysız yürütme"], risk_level=RiskLevel.HIGH,
                      requires_user_approval=True, source="native",
                      usable_by_brains=["Engineering", "Executive", "Operations"])


def register_native(orchestrator, capabilities: CapabilityRegistry, capability: Capability,
                    executor) -> Capability:
    """Bir native yeteneği sisteme ekler (Capability + executor). MCP ile aynı soyutlama."""
    capabilities.register(capability)
    orchestrator.register_executor(capability.name, executor)
    return capability
