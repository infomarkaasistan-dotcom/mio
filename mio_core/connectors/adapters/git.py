"""MIO Core · System Connector · Git — GERÇEK git işlemleri (git CLI, subprocess).

capability: git.clone (+ git.status yardımcı). git yoksa health=False → Manager sağlıksız connector'ı atlar.
git.clone yüksek-risk sayılmaz ama uzak repo yazımı içeren işler Madde 24'e girer (ör. github.pr ayrı connector)."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Callable

from ..models import CallableConnector, ConnectorCategory, ValidationError

CAP_STATUS = "git.status"


def git_connector(*, name: str = "git", priority: int = 100, timeout: float = 120.0,
                  runner: Callable = subprocess.run) -> CallableConnector:
    def _run(args: list, cwd=None) -> dict[str, Any]:
        proc = runner(["git", *args], capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return {"returncode": proc.returncode, "stdout": (proc.stdout or "")[:8000],
                "stderr": (proc.stderr or "")[:4000]}

    def _clone(req: dict) -> dict[str, Any]:
        url = req.get("url")
        dest = req.get("dest")
        if not url or not dest:
            raise ValidationError("git.clone: url ve dest gerekli")
        return _run(["clone", str(url), str(dest)])

    def _status(req: dict) -> dict[str, Any]:
        return _run(["status", "--porcelain"], cwd=req.get("cwd"))

    from ..models import Cap
    return CallableConnector(
        name=name, category=ConnectorCategory.SYSTEM,
        handlers={Cap.GIT_CLONE: _clone, CAP_STATUS: _status},
        priority=priority, health_fn=lambda: shutil.which("git") is not None)


__all__ = ["git_connector", "CAP_STATUS"]
