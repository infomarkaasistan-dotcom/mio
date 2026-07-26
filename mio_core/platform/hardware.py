"""MIO Core · Platform · Hardware Diagnostics & Awareness — stdlib + subprocess, DETERMİNİSTİK (enjekte-edilebilir).

Başlangıçta/CLI'dan sistem kaynaklarını analiz eder: CPU · RAM · GPU/VRAM · CUDA · Ollama durumu + **model
CPU'da mı GPU'da mı çalışıyor** tespiti. Model CPU'da/kısmi çalışıyorsa UYARIR ve GPU tabanlı yapılandırma önerir;
uygun modeli seçmeden önce VRAM'e göre öneri verir. `runner` (subprocess) ve `urlopen` enjekte edilebilir → testler
gerçek donanım gerektirmez. Çekirdek iş mantığı değil; bir GÖZLEM/TEŞHİS katmanıdır (karar Executive'de)."""

from __future__ import annotations

import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# --------------------------------------------------------------------------- #
def _run(args: list, runner: Callable, timeout: float = 8.0) -> Optional[str]:
    try:
        proc = runner(args, capture_output=True, text=True, timeout=timeout)
        return proc.stdout if proc.returncode == 0 else None
    except Exception:  # noqa: BLE001 — araç yok/hata → tespit edilemedi (dürüst None)
        return None


@dataclass
class GpuInfo:
    name: str
    memory_total_mb: int = 0
    memory_used_mb: int = 0
    utilization_pct: int = 0

    @property
    def memory_free_mb(self) -> int:
        return max(0, self.memory_total_mb - self.memory_used_mb)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "memory_total_mb": self.memory_total_mb,
                "memory_used_mb": self.memory_used_mb, "memory_free_mb": self.memory_free_mb,
                "utilization_pct": self.utilization_pct}


def detect_gpus(*, runner: Callable = subprocess.run) -> list[GpuInfo]:
    """NVIDIA GPU'ları (nvidia-smi). nvidia-smi yoksa boş liste (NVIDIA GPU yok/erişilemez — dürüst)."""
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits"], runner)
    if not out:
        return []
    gpus: list[GpuInfo] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            try:
                gpus.append(GpuInfo(name=parts[0], memory_total_mb=int(float(parts[1])),
                                    memory_used_mb=int(float(parts[2])), utilization_pct=int(float(parts[3]))))
            except ValueError:
                continue
    return gpus


def detect_cuda(*, runner: Callable = subprocess.run) -> dict[str, Any]:
    out = _run(["nvidia-smi"], runner)
    if out:
        m = re.search(r"CUDA Version:\s*([\d.]+)", out)
        if m:
            return {"available": True, "version": m.group(1)}
    return {"available": False, "version": None}


def detect_cpu() -> dict[str, Any]:
    name = platform.processor() or ""
    if not name and os.path.exists("/proc/cpuinfo"):
        try:
            for line in open("/proc/cpuinfo", encoding="utf-8"):
                if line.lower().startswith("model name"):
                    name = line.split(":", 1)[1].strip()
                    break
        except Exception:  # noqa: BLE001
            pass
    return {"cores": os.cpu_count() or 0, "name": name or platform.machine(), "arch": platform.machine()}


def detect_ram() -> dict[str, Any]:
    """Toplam/boş fiziksel RAM (MB). Windows: ctypes; Linux: /proc/meminfo; aksi: bilinmiyor (dürüst)."""
    try:
        if os.name == "nt":
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = _MS()
            st.dwLength = ctypes.sizeof(_MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return {"total_mb": st.ullTotalPhys // (1024 * 1024),
                    "available_mb": st.ullAvailPhys // (1024 * 1024)}
        if os.path.exists("/proc/meminfo"):
            info = {}
            for line in open("/proc/meminfo", encoding="utf-8"):
                k, _, v = line.partition(":")
                info[k.strip()] = int(v.strip().split()[0]) // 1024  # kB → MB
            return {"total_mb": info.get("MemTotal", 0),
                    "available_mb": info.get("MemAvailable", info.get("MemFree", 0))}
    except Exception:  # noqa: BLE001
        pass
    return {"total_mb": 0, "available_mb": 0}


def _classify_placement(size: int, size_vram: int) -> str:
    """Ollama modeli GPU'da mı CPU'da mı: size_vram/size oranı."""
    if size <= 0:
        return "unknown"
    ratio = size_vram / size
    if ratio >= 0.9:
        return "gpu"
    if ratio <= 0.1:
        return "cpu"
    return "partial"                      # kısmi offload — yavaş


def detect_ollama(*, host: str = "http://localhost:11434", urlopen: Optional[Callable] = None) -> dict[str, Any]:
    """Ollama sürümü + YÜKLÜ modeller ve her birinin CPU/GPU yerleşimi (/api/ps)."""
    from mio_core.connectors.adapters._http import http_json
    base = host.rstrip("/")
    result: dict[str, Any] = {"reachable": False, "version": None, "loaded_models": []}
    try:
        ver = http_json(f"{base}/api/version", timeout=3, urlopen=urlopen)
        result["reachable"] = True
        result["version"] = ver["body"].get("version")
    except Exception:  # noqa: BLE001 — Ollama kapalı (dürüst)
        return result
    try:
        ps = http_json(f"{base}/api/ps", timeout=3, urlopen=urlopen)["body"]
        for m in ps.get("models", []):
            size, vram = int(m.get("size", 0)), int(m.get("size_vram", 0))
            result["loaded_models"].append({
                "name": m.get("name"), "size_gb": round(size / 1e9, 2),
                "size_vram_gb": round(vram / 1e9, 2), "placement": _classify_placement(size, vram)})
    except Exception:  # noqa: BLE001
        pass
    return result


# --------------------------------------------------------------------------- #
def _params_billion(model_name: str) -> Optional[float]:
    """Model adından yaklaşık parametre sayısı (ör. 'llama3.2:3b' → 3.0)."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*b\b", (model_name or "").lower())
    return float(m.group(1)) if m else None


def _vram_need_mb(params_b: float) -> int:
    """q4 nicemleme kabası: ~0.7 GB / B params + ~0.7 GB overhead (context/kv)."""
    return int(params_b * 700 + 700)


class HardwareDiagnostics:
    """Donanım farkındalığı + yerel çıkarım teşhisi. `runner`/`urlopen` enjekte edilebilir → deterministik test."""

    def __init__(self, *, runner: Callable = subprocess.run, urlopen: Optional[Callable] = None,
                 ollama_host: str = "http://localhost:11434") -> None:
        self._runner = runner
        self._urlopen = urlopen
        self._host = ollama_host

    def report(self) -> dict[str, Any]:
        cpu = detect_cpu()
        ram = detect_ram()
        gpus = [g.to_dict() for g in detect_gpus(runner=self._runner)]
        cuda = detect_cuda(runner=self._runner)
        ollama = detect_ollama(host=self._host, urlopen=self._urlopen)
        warnings, recs = self._advise(gpus, cuda, ram, ollama)
        return {"cpu": cpu, "ram": ram, "gpus": gpus, "cuda": cuda, "ollama": ollama,
                "warnings": warnings, "recommendations": recs,
                "gpu_available": bool(gpus), "platform": platform.system()}

    def _advise(self, gpus: list, cuda: dict, ram: dict, ollama: dict) -> tuple[list, list]:
        warnings: list = []
        recs: list = []
        loaded = ollama.get("loaded_models", [])
        cpu_or_partial = [m for m in loaded if m["placement"] in ("cpu", "partial")]

        if not gpus:
            warnings.append("GPU tespit edilmedi (nvidia-smi yok). Yerel LLM çıkarımı CPU'da çalışır — ÇOK YAVAŞ "
                            "olabilir ve sistem donabilir.")
            recs.append("Küçük model (≤3B) + kısa prompt kullanın; ağır modellerden kaçının. GPU tabanlı "
                        "yapılandırma için NVIDIA sürücü + CUDA + Ollama GPU desteği gerekir.")
        else:
            free = min((g["memory_free_mb"] for g in gpus), default=0)
            if cpu_or_partial:
                names = ", ".join(m["name"] for m in cpu_or_partial)
                warnings.append(f"GPU MEVCUT ama model(ler) CPU'da/kısmi çalışıyor: {names}. Bu, VRAM yetersizliği "
                                "(başka modeller yüklü) ya da GPU offload kapalı demektir — YAVAŞ.")
                recs.append("OLLAMA_MAX_LOADED_MODELS=1 ile tek model tutun; kullanılmayan modelleri boşaltın "
                            "(ollama stop); VRAM'e sığan model seçin. Gerekirse OLLAMA_NUM_GPU/gpu_layers ayarlayın.")
            if not cuda.get("available"):
                warnings.append("GPU var ama CUDA tespit edilemedi — Ollama GPU'yu kullanamıyor olabilir.")
                recs.append("NVIDIA sürücü + CUDA kurulumunu doğrulayın (nvidia-smi CUDA Version görünmeli).")
            if free and free < 2500:
                warnings.append(f"GPU boş VRAM düşük (~{free} MB) — modeller CPU'ya taşabilir.")
        return warnings, recs

    def recommend_model(self, models: list) -> dict[str, Any]:
        """Mevcut modeller arasından VRAM'e SIĞAN en büyüğünü önerir (GPU yoksa en küçüğü + uyarı)."""
        gpus = detect_gpus(runner=self._runner)
        vram_free = min((g.memory_free_mb for g in gpus), default=0) if gpus else 0
        budget = vram_free - 500 if gpus else 0    # headroom
        scored = []
        for name in models:
            pb = _params_billion(name)
            need = _vram_need_mb(pb) if pb else 999999
            scored.append({"model": name, "params_b": pb, "vram_need_mb": need,
                           "fits_gpu": bool(gpus) and need <= budget})
        fitting = [s for s in scored if s["fits_gpu"]]
        if fitting:
            best = max(fitting, key=lambda s: s["params_b"] or 0)
            return {"recommended": best["model"], "reason": "VRAM'e sığan en yetenekli model",
                    "gpu": True, "vram_free_mb": vram_free, "candidates": scored}
        # GPU yok ya da hiçbiri sığmıyor → en küçük + uyarı
        smallest = min((s for s in scored if s["params_b"]), key=lambda s: s["params_b"], default=None)
        return {"recommended": smallest["model"] if smallest else (models[0] if models else None),
                "reason": "GPU'ya sığan model yok — CPU çıkarımı YAVAŞ; en küçük model önerildi",
                "gpu": bool(gpus), "vram_free_mb": vram_free, "warning": True, "candidates": scored}


__all__ = ["HardwareDiagnostics", "GpuInfo", "detect_gpus", "detect_cpu", "detect_ram", "detect_cuda",
           "detect_ollama"]
