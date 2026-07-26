"""MIO Core · Donanım keşfi — GERÇEK sistem (üretim), stdlib + opsiyonel psutil.

Kurulumda keşfedilen bilgi (ADR-0002 katman 2): CPU/RAM/GPU/platform → Self Awareness'a beslenir. Belirlenemeyen
alan dürüstçe atlanır/"unknown" olur (uydurma yok). Ek bağımlılık zorunlu değildir (psutil varsa RAM eklenir)."""

from __future__ import annotations

import os
import platform
import shutil
from typing import Any


def discover_hardware() -> dict[str, Any]:
    """GERÇEK donanım/platform bilgisini toplar. Yalnız belirlenebilenler döner (dürüst)."""
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }

    # RAM — psutil varsa gerçek toplam/uygun; yoksa dürüstçe atla.
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        info["ram_total_gb"] = round(vm.total / 1e9, 1)
        info["ram_available_gb"] = round(vm.available / 1e9, 1)
        info["cpu_percent"] = psutil.cpu_percent(interval=None)
    except Exception:  # noqa: BLE001 — psutil yoksa RAM alanları eklenmez (dürüst)
        pass

    # GPU — best-effort: nvidia-smi varlığı (kesin sayım için ayrı iş).
    if shutil.which("nvidia-smi"):
        info["gpu"] = "nvidia"
    elif platform.system() == "Darwin" and platform.machine() == "arm64":
        info["gpu"] = "apple_silicon"
    else:
        info["gpu"] = "unknown"

    return info


__all__ = ["discover_hardware"]
