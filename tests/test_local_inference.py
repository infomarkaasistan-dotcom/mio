"""MIO Core · Local Inference Manager — MIO çalışacağı ORTAMI yönetir. Üretim testleri (enjekte → deterministik).

Gerçek indirme/çıkarım/silme YOK: ollama CLI (runner) ve HTTP (urlopen) enjekte edilir. Doğrulanan: analiz, uygun
model seçimi (VRAM), fazlalık durdurma (güvenli), eksik model indirme, sağlık+hız testi, SİLME/KURULUM Madde 24
onay kapısı, donma önleme (GPU'ya sığmıyorsa ağır test atlanır)."""

import json

import pytest

from mio_core.platform.hardware import HardwareDiagnostics
from mio_core.platform.local_inference import LocalInferenceManager, FAST_THRESHOLD_MS


class _Proc:
    def __init__(self, stdout="", rc=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, rc, stderr


class _Resp:
    def __init__(self, payload):
        self._p = json.dumps(payload).encode("utf-8"); self.status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return self._p


_GPU8 = "NVIDIA GeForce RTX 3050, 8192, 1166, 6\n"
_SMI = "CUDA Version: 13.1\n"


def _hw(gpu_csv=_GPU8, smi=_SMI):
    def run(args, capture_output=True, text=True, timeout=8):
        if args[:1] == ["nvidia-smi"]:
            if any("query-gpu" in a for a in args):
                return _Proc(gpu_csv, 0 if gpu_csv else 1)
            return _Proc(smi, 0 if smi else 1)
        return _Proc("", 1)
    return HardwareDiagnostics(runner=run)


def _ollama_urlopen(*, reachable=True, tags=None, ps=None, gen_response="pong", gen_delay_flag=None):
    calls = {"generate": []}

    def op(req, timeout=30):
        url = req.full_url
        if url.endswith("/api/version"):
            if not reachable:
                raise OSError("connection refused")
            return _Resp({"version": "0.32.3"})
        if url.endswith("/api/tags"):
            return _Resp({"models": [{"name": n} for n in (tags or [])]})
        if url.endswith("/api/ps"):
            return _Resp({"models": ps or []})
        if url.endswith("/api/generate"):
            body = json.loads(req.data.decode())
            calls["generate"].append(body)
            return _Resp({"response": gen_response, "model": body.get("model")})
        if url.endswith("/api/delete"):
            return _Resp({})
        raise OSError(f"unexpected {url}")
    op.calls = calls
    return op


def _mgr(hw=None, runner=None, urlopen=None):
    runner = runner or (lambda *a, **k: _Proc("", 0))
    return LocalInferenceManager(hw or _hw(), runner=runner, urlopen=urlopen)


# ---- analiz (salt-okunur) ----
def test_analyze_reports_env():
    m = _mgr(urlopen=_ollama_urlopen(tags=["mistral:7b"], ps=[
        {"name": "mistral:7b", "size": 5000000000, "size_vram": 5000000000}]))
    a = m.analyze()
    assert a["ollama_reachable"] is True and "mistral:7b" in a["installed_models"]
    assert a["loaded_models"][0]["placement"] == "gpu"
    assert a["hardware"]["gpu_available"] is True


# ---- Ollama yoksa: kurulum ONAY ister (Madde 24), otomatik kurmaz ----
def test_ollama_missing_requires_install_approval():
    # reachable False + ollama --version de başarısız → kurulu değil
    m = _mgr(runner=lambda *a, **k: _Proc("", 1), urlopen=_ollama_urlopen(reachable=False))
    rep = m.ensure_ready()
    assert rep["ready"] is False
    pend = [p for p in rep["pending_approval"] if p["action"] == "install_ollama"]
    assert len(pend) == 1 and pend[0]["requires_approval"] is True
    assert "command" in pend[0]                            # elle kurulum komutu önerilir


# ---- seçim + eksik model indirme + test BAŞARILI (GPU, hızlı) ----
def test_ensure_ready_selects_pulls_tests_success():
    pulled = {"n": 0}
    def runner(args, capture_output=True, text=True, timeout=600):
        if args[:2] == ["ollama", "pull"]:
            pulled["n"] += 1; return _Proc("success", 0)
        return _Proc("", 0)
    # kurulu model yok → aday havuzdan VRAM'e sığan EN YETENEKLİ seçilir (8GB → llama3.1:8b sığar) → pull → test
    up = _ollama_urlopen(tags=[], ps=[{"name": "llama3.1:8b", "size": 5e9, "size_vram": 5e9}])
    m = _mgr(runner=runner, urlopen=up)
    rep = m.ensure_ready()
    assert rep["selected_model"] == "llama3.1:8b"          # en büyük-sığan (8B, ~6.3GB < 6.5GB bütçe)
    assert any(a["action"] == "pull_model" for a in rep["actions_executed"])
    assert pulled["n"] == 1
    assert rep["ready"] is True and "TEST BAŞARILI" in rep["message"] and "Ollama bağlı" in rep["message"]
    assert rep["test"]["placement"] == "gpu" and rep["test"]["fast"] is True


# ---- fazlalık modelleri DURDUR (güvenli, VRAM boşalt) ----
def test_ensure_ready_stops_other_loaded_models():
    stops = []
    up = _ollama_urlopen(tags=["mistral:7b"], ps=[
        {"name": "mistral:7b", "size": 5e9, "size_vram": 5e9},
        {"name": "qwen3:14b", "size": 9e9, "size_vram": 2e9}])   # fazlalık, kısmi
    m = _mgr(urlopen=up)
    orig_stop = m.stop_model
    m.stop_model = lambda n: stops.append(n) or {"ok": True}
    rep = m.ensure_ready()
    assert "qwen3:14b" in stops                            # seçili olmayan yüklü model durduruldu
    assert "mistral:7b" not in stops                       # seçili durdurulmaz


# ---- SİLME onay ister (Madde 24); onaysız yalnız ÖNERİLİR ----
def test_delete_requires_approval():
    # sığan (mistral:7b) + sığmayan (qwen3:14b) birlikte kurulu → 7b seçilir, 14b silme adayı ÖNERİLİR
    m = _mgr(urlopen=_ollama_urlopen(tags=["mistral:7b", "qwen3:14b"], ps=[]))
    rep = m.ensure_ready(run_test=False)
    assert rep["selected_model"] == "mistral:7b"
    pend = [p for p in rep["pending_approval"] if p["action"] == "delete_model"]
    assert any(p["model"] == "qwen3:14b" and p["requires_approval"] for p in pend)   # önerilir, silinmez
    # doğrudan delete: onaysız reddedilir (Madde 24)
    assert m.delete_model("qwen3:14b")["status"] == "requires_approval"
    # onaylı: silinir
    assert m.delete_model("qwen3:14b", user_approved=True)["ok"] is True


# ---- donma önleme: GPU yok → ağır test ATLANIR ----
def test_no_gpu_skips_heavy_test():
    m = _mgr(hw=_hw(gpu_csv=""), urlopen=_ollama_urlopen(tags=["llama3.2:3b"], ps=[]))
    rep = m.ensure_ready()
    assert rep["test"] is None                            # test atlandı (donma önleme)
    assert any("test ATLANDI" in w or "YAVAŞ" in w for w in rep["warnings"])
    assert rep["ready"] is False


# ---- test yavaş/CPU → ready False + uyarı ----
def test_slow_cpu_placement_not_ready():
    up = _ollama_urlopen(tags=["mistral:7b"],
                         ps=[{"name": "mistral:7b", "size": 5e9, "size_vram": 0}])   # CPU yerleşim
    m = _mgr(urlopen=up)
    rep = m.ensure_ready()
    # test çalışır (fits_gpu true çünkü VRAM boş 7GB) ama yerleşim cpu → ready False
    assert rep["test"]["ok"] is True and rep["test"]["placement"] == "cpu"
    assert rep["ready"] is False


# ---- entegrasyon: boot + CLI + HTTP paylaşımı ----
def test_via_runtime_and_shared_surface(tmp_path):
    from mio_core.runtime import boot
    from mio_core import appservice
    from mio_core.cli import run_command
    from mio_core.http_api import route_request
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        # gerçek makinede analyze salt-okunur çalışır (indirme/çıkarım yok)
        a = appservice.inference_analyze(mio)
        assert "hardware" in a and "installed_models" in a
        assert run_command(mio, ["inference", "analyze"])[0] == 0
        st, data = route_request(mio, "GET", "/inference/analyze", {}, None)
        assert st == 200 and "ollama_reachable" in data
    finally:
        mio.close()
