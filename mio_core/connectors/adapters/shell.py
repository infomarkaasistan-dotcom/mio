"""MIO Core · System Connector · Shell — GERÇEK komut çalıştırma (subprocess), zaman-aşımı korumalı.

capability: shell.exec. YÜKSEK-RİSK (Connector Manager Madde 24 kapısı: onaysız çalışmaz). `runner` enjekte
edilebilir (test). Komut liste ya da string olabilir; string ise shell=False güvenliği için argümanlara bölünür."""

from __future__ import annotations

import shlex
import subprocess
from typing import Any, Callable

from ..models import Cap, CallableConnector, ConnectorCategory, ValidationError


def shell_connector(*, name: str = "shell", priority: int = 100, timeout: float = 30.0,
                    runner: Callable = subprocess.run) -> CallableConnector:
    def _exec(req: dict) -> dict[str, Any]:
        cmd = req.get("cmd")
        if not cmd:
            raise ValidationError("cmd boş olamaz")
        args = cmd if isinstance(cmd, list) else shlex.split(str(cmd))
        proc = runner(args, capture_output=True, text=True, timeout=req.get("timeout", timeout))
        return {"returncode": proc.returncode,
                "stdout": (proc.stdout or "")[:8000], "stderr": (proc.stderr or "")[:4000]}

    return CallableConnector(
        name=name, category=ConnectorCategory.SYSTEM,
        handlers={Cap.SHELL_EXEC: _exec}, priority=priority, health_fn=lambda: True)


__all__ = ["shell_connector"]
