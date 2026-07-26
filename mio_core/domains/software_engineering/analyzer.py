"""MIO Core · Software Engineering · Kod Analizörü — DETERMİNİSTİK, stdlib-only (ast + re), LLM-BAĞIMSIZ.

GERÇEK statik analiz: Python için `ast` (fonksiyon/sınıf/docstring/karmaşıklık + placeholder/stub tespiti);
diğer diller için satır+desen tabanlı. Anayasa 'placeholder yok' kuralını ölçülebilir kılar."""

from __future__ import annotations

import ast
import re
from typing import Any

# Metin-tabanlı placeholder desenleri (Anayasa: placeholder/mock/stub/TODO yok)
_TEXT_PATTERNS = [(re.compile(rf"\b{w}\b", re.IGNORECASE), w) for w in
                  ("TODO", "FIXME", "XXX", "HACK", "placeholder", "stub", "dummy", "mock")]


def _branch_complexity(tree: ast.AST) -> int:
    """Kaba döngüsel karmaşıklık: dallanma düğümü sayısı + 1 (deterministik)."""
    n = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try,
                             ast.With, ast.AsyncWith, ast.ExceptHandler, ast.BoolOp)):
            n += 1
    return n


def _body_without_docstring(node) -> list:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _stub_issue(node) -> str | None:
    """Bir fonksiyon/sınıfın gövdesi yalnız placeholder mı? (pass / ... / raise NotImplementedError)."""
    body = _body_without_docstring(node)
    if len(body) != 1:
        return None
    only = body[0]
    if isinstance(only, ast.Pass):
        return "pass-only"
    if isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant) and only.value.value is Ellipsis:
        return "ellipsis"
    if isinstance(only, ast.Raise):
        exc = only.exc
        name = getattr(getattr(exc, "func", exc), "id", None) or getattr(exc, "id", None)
        if name == "NotImplementedError":
            return "not-implemented"
    return None


def analyze(source: str, *, language: str = "python") -> dict[str, Any]:
    """Deterministik statik analiz raporu. Aynı kaynak → aynı rapor."""
    source = source or ""
    lines = source.splitlines()
    loc = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    issues: list[dict[str, Any]] = []

    # Metin-tabanlı placeholder taraması (tüm diller)
    for i, ln in enumerate(lines, 1):
        for pat, label in _TEXT_PATTERNS:
            if pat.search(ln):
                issues.append({"kind": "placeholder", "marker": label, "line": i,
                               "detail": ln.strip()[:100]})

    metrics: dict[str, Any] = {"loc": loc, "lines": len(lines), "functions": 0, "classes": 0,
                               "complexity": 1, "docstring_coverage": 1.0}

    if language == "python":
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            issues.append({"kind": "syntax_error", "line": getattr(exc, "lineno", 0),
                           "detail": str(exc)[:120]})
            return {"language": language, "valid": False, "metrics": metrics, "issues": issues,
                    "issue_count": len(issues)}
        defs = [n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        funcs = [n for n in defs if not isinstance(n, ast.ClassDef)]
        classes = [n for n in defs if isinstance(n, ast.ClassDef)]
        documented = sum(1 for n in defs if ast.get_docstring(n))
        for n in defs:
            stub = _stub_issue(n)
            if stub is not None:
                issues.append({"kind": "stub", "marker": stub, "line": getattr(n, "lineno", 0),
                               "detail": f"{type(n).__name__} '{getattr(n, 'name', '?')}' gövdesi placeholder ({stub})"})
        metrics.update({"functions": len(funcs), "classes": len(classes),
                        "complexity": _branch_complexity(tree),
                        "docstring_coverage": round(documented / len(defs), 3) if defs else 1.0})
        return {"language": language, "valid": True, "metrics": metrics, "issues": issues,
                "issue_count": len(issues)}

    # Python-dışı: yalnız satır+desen analizi (dürüst — derin analiz yok)
    return {"language": language, "valid": True, "metrics": metrics, "issues": issues,
            "issue_count": len(issues)}


__all__ = ["analyze"]
