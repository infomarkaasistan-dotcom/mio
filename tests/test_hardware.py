"""MIO Core · Hardware Diagnostics & Awareness — üretim testleri (enjekte runner/urlopen → deterministik).

Gerçek donanım gerektirmez: nvidia-smi çıktısı ve Ollama /api/ps enjekte edilir. GPU parse, CPU-vs-GPU çıkarım
sınıflandırma (size_vram/size), uyarı/öneri mantığı, model önerisi ve canlı-güvenli davranış doğrulanır."""

import json

import pytest

from mio_core.platform.hardware import (
    HardwareDiagnostics,
    detect_cpu,
    detect_gpus,
    detect_ram,
)


class _Proc:
    def __init__(self, stdout: str, rc: int = 0):
        self.stdout = stdout
        self.returncode = rc
        self.stderr = ""


def _runner(*, gpu_csv: str = "", smi: str = "", ok: bool = True):
    def run(args, capture_output=True, text=True, timeout=8):
        if args and args[0] == "nvidia-smi":
            if any("query-gpu" in a for a in args):
                return _Proc(gpu_csv, 0 if gpu_csv else 1)
            return _Proc(smi, 0 if smi else 1)
        return _Proc("", 1)
    return run


class _Resp:
    def __init__(self, payload):
        self._p = json.dumps(payload).encode("utf-8")
        self.status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return self._p


def _urlopen(*, version="0.32.3", ps_models=None):
    def op(req, timeout=30):
        url = req.full_url
        if url.endswith("/api/version"):
            return _Resp({"version": version})
        if url.endswith("/api/ps"):
            return _Resp({"models": ps_models or []})
        raise OSError("unexpected url")
    return op


_GPU_CSV = "NVIDIA GeForce RTX 3050, 8192, 1166, 6\n"
_SMI = "CUDA Version: 13.1 ...\n"


# ---- GPU / CPU / RAM tespiti ----
def test_detect_gpus_parses_nvidia_smi():
    gpus = detect_gpus(runner=_runner(gpu_csv=_GPU_CSV))
    assert len(gpus) == 1
    g = gpus[0]
    assert "RTX 3050" in g.name and g.memory_total_mb == 8192 and g.memory_free_mb == 8192 - 1166


def test_detect_gpus_none_when_no_nvidia_smi():
    assert detect_gpus(runner=_runner(gpu_csv="")) == []


def test_detect_cpu_and_ram_real_read_only():
    cpu = detect_cpu()
    assert cpu["cores"] >= 1 and isinstance(cpu["name"], str)
    ram = detect_ram()
    assert ram["total_mb"] >= 0 and ram["available_mb"] >= 0


# ---- CPU-vs-GPU çıkarım sınıflandırma (asıl teşhis) ----
def test_ollama_placement_gpu_cpu_partial():
    d = HardwareDiagnostics(runner=_runner(gpu_csv=_GPU_CSV, smi=_SMI),
                            urlopen=_urlopen(ps_models=[
                                {"name": "gpu-model", "size": 1000, "size_vram": 1000},   # tam GPU
                                {"name": "cpu-model", "size": 1000, "size_vram": 0},       # tam CPU
                                {"name": "partial-model", "size": 1000, "size_vram": 500}, # kısmi
                            ]))
    ollama = d.report()["ollama"]
    place = {m["name"]: m["placement"] for m in ollama["loaded_models"]}
    assert place == {"gpu-model": "gpu", "cpu-model": "cpu", "partial-model": "partial"}


# ---- uyarı: GPU var ama model CPU'da (kullanıcının yaşadığı durum) ----
def test_warns_when_gpu_present_but_model_on_cpu():
    d = HardwareDiagnostics(runner=_runner(gpu_csv=_GPU_CSV, smi=_SMI),
                            urlopen=_urlopen(ps_models=[{"name": "big", "size": 1000, "size_vram": 50}]))
    rep = d.report()
    assert rep["gpu_available"] is True
    assert any("CPU'da/kısmi" in w for w in rep["warnings"])
    assert any("OLLAMA_MAX_LOADED_MODELS" in r for r in rep["recommendations"])


# ---- uyarı: GPU yok → CPU çıkarımı yavaş (donma riski) ----
def test_warns_when_no_gpu():
    d = HardwareDiagnostics(runner=_runner(gpu_csv=""), urlopen=_urlopen(ps_models=[]))
    rep = d.report()
    assert rep["gpu_available"] is False
    assert any("CPU'da çalışır" in w or "ÇOK YAVAŞ" in w for w in rep["warnings"])


# ---- model önerisi: VRAM'e göre ----
def test_recommend_model_fits_vram():
    d = HardwareDiagnostics(runner=_runner(gpu_csv=_GPU_CSV, smi=_SMI))
    rec = d.recommend_model(["llama3.2:3b", "mistral:7b", "qwen3:14b"])
    # 8GB VRAM (~7GB boş) → 14B sığmaz, 7B en yetenekli-sığan
    assert rec["gpu"] is True and rec["recommended"] == "mistral:7b"


def test_recommend_model_no_gpu_warns():
    d = HardwareDiagnostics(runner=_runner(gpu_csv=""))
    rec = d.recommend_model(["llama3.2:3b", "mistral:7b"])
    assert rec.get("warning") is True and rec["recommended"] == "llama3.2:3b"   # en küçük


# ---- entegrasyon: boot + appservice/CLI/HTTP paylaşımı ----
def test_via_runtime_and_shared_surface(tmp_path):
    from mio_core.runtime import boot
    from mio_core import appservice
    from mio_core.cli import run_command
    from mio_core.http_api import route_request
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        # gerçek makinede çalışır (read-only teşhis); anahtarlar mevcut
        rep = appservice.hardware_report(mio)
        for key in ("cpu", "ram", "gpus", "cuda", "ollama", "warnings", "recommendations", "gpu_available"):
            assert key in rep
        assert run_command(mio, ["hardware"])[0] == 0
        st, data = route_request(mio, "GET", "/hardware", {}, None)
        assert st == 200 and "cpu" in data
    finally:
        mio.close()
