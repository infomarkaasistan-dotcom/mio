"""MIO Core · Platform · Local Inference Manager — MIO çalışacağı ORTAMI yönetir (Ollama + modeller).

MIO sistemi tanır ve yerel çıkarım ortamını hazırlar: analiz → uygun modeli SEÇ → fazla/CPU'da yüklü modelleri
DURDUR (VRAM boşalt, güvenli) → eksikse İNDİR (additive) → sağlık+HIZ TESTİ (yalnız GPU'ya sığıyorsa — donma
önleme) → başarılıysa "Ollama bağlı" bildir.

**Anayasa:** Executive tek karar verici; seçim DETERMİNİSTİK (VRAM'e göre, LLM'siz). **Geri-alınamaz işler ONAY
ister (Madde 24):** model SİLME ve Ollama KURULUMU — MIO bunları sessizce YAPMAZ, önerir; yalnız açık onayla
yürütür. Güvenli işler (analiz/stop/pull/test) otomatik. `runner`/`urlopen` enjekte edilebilir → deterministik test
(gerçek çıkarım/indirme olmadan)."""

from __future__ import annotations

import subprocess
import time
from typing import Any, Callable, Optional

from .hardware import HardwareDiagnostics, detect_ollama

# GPU'da küçük prompt (num_predict=8) için "hızlı/sağlıklı" eşiği
FAST_THRESHOLD_MS = 8000
# Hiç model kurulu değilse VRAM'e göre değerlendirilecek güvenli aday havuzu (küçükten büyüğe)
DEFAULT_CANDIDATES = ["llama3.2:3b", "qwen2.5:3b", "mistral:7b", "llama3.1:8b"]


class LocalInferenceManager:
    def __init__(self, hardware: HardwareDiagnostics, *, host: str = "http://localhost:11434",
                 runner: Callable = subprocess.run, urlopen: Optional[Callable] = None) -> None:
        self._hw = hardware
        self._host = host.rstrip("/")
        self._runner = runner
        self._urlopen = urlopen

    # -- düşük seviye (enjekte-edilebilir) ------------------------------- #
    def _api(self, path: str, *, method: str = "GET", body: Any = None, timeout: float = 30.0) -> dict:
        from mio_core.connectors.adapters._http import http_json
        return http_json(f"{self._host}{path}", method=method, body=body, timeout=timeout,
                         urlopen=self._urlopen)

    def _cli(self, args: list, timeout: float = 600.0) -> dict[str, Any]:
        try:
            p = self._runner(["ollama", *args], capture_output=True, text=True, timeout=timeout)
            return {"ok": p.returncode == 0, "stdout": (p.stdout or "")[:2000],
                    "stderr": (p.stderr or "")[:1000]}
        except Exception as exc:  # noqa: BLE001 — ollama CLI yok/hata → görünür (dürüst)
            return {"ok": False, "error": str(exc)[:200]}

    def ollama_reachable(self) -> bool:
        try:
            return 200 <= self._api("/api/version", timeout=3)["status"] < 300
        except Exception:  # noqa: BLE001
            return False

    def ollama_installed(self) -> bool:
        return self.ollama_reachable() or self._cli(["--version"], timeout=8).get("ok", False)

    def installed_models(self) -> list:
        try:
            return [m.get("name") for m in self._api("/api/tags", timeout=5)["body"].get("models", [])]
        except Exception:  # noqa: BLE001
            return []

    def loaded_models(self) -> list:
        return detect_ollama(host=self._host, urlopen=self._urlopen).get("loaded_models", [])

    # -- eylemler -------------------------------------------------------- #
    def stop_model(self, name: str) -> dict[str, Any]:
        """VRAM'den boşalt (keep_alive=0) — GÜVENLİ/geri-alınabilir (sadece bellekten düşer)."""
        try:
            self._api("/api/generate", method="POST", body={"model": name, "keep_alive": 0}, timeout=15)
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:160]}

    def pull_model(self, name: str) -> dict[str, Any]:
        """Modeli indir — additive (yıkıcı değil). ollama pull (CLI, uzun timeout)."""
        return self._cli(["pull", name], timeout=1800)

    def delete_model(self, name: str, *, user_approved: bool = False) -> dict[str, Any]:
        """Modeli cihazdan SİL — GERİ ALINAMAZ → ONAY ister (Madde 24)."""
        if not user_approved:
            return {"ok": False, "status": "requires_approval",
                    "message": f"{name} silme geri-alınamaz — onay gerekli (Madde 24)"}
        try:
            r = self._api("/api/delete", method="DELETE", body={"name": name}, timeout=30)
            return {"ok": 200 <= r["status"] < 300, "status": "deleted"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:160]}

    def test_model(self, name: str) -> dict[str, Any]:
        """Sağlık+HIZ testi: küçük prompt (num_predict=8), süre + CPU/GPU yerleşimi ölç. Sınırlı → güvenli."""
        start = time.perf_counter()
        try:
            r = self._api("/api/generate", method="POST",
                          body={"model": name, "prompt": "ping", "stream": False,
                                "options": {"num_predict": 8}}, timeout=120)
        except Exception as exc:  # noqa: BLE001 — test hatası görünür, çökmez
            return {"ok": False, "error": str(exc)[:200],
                    "latency_ms": int((time.perf_counter() - start) * 1000)}
        latency = int((time.perf_counter() - start) * 1000)
        body = r["body"]
        placement = next((m["placement"] for m in self.loaded_models()
                          if m["name"] == name or m["name"].startswith(name.split(":")[0])), "unknown")
        return {"ok": "response" in body, "latency_ms": latency, "placement": placement,
                "fast": latency <= FAST_THRESHOLD_MS, "response_len": len(body.get("response", ""))}

    def _install_command(self) -> str:
        import platform as _pf
        sysname = _pf.system()
        if sysname == "Windows":
            return "winget install --id Ollama.Ollama -e  (veya https://ollama.com/download)"
        if sysname == "Darwin":
            return "brew install ollama  (veya https://ollama.com/download)"
        return "curl -fsSL https://ollama.com/install.sh | sh"

    # -- analiz / plan / hazırla ---------------------------------------- #
    def analyze(self) -> dict[str, Any]:
        """Salt-okunur ortam analizi: donanım + Ollama + kurulu/yüklü modeller + yerleşim."""
        hw = self._hw.report()
        return {"hardware": hw, "ollama_reachable": self.ollama_reachable(),
                "ollama_installed": self.ollama_installed(),
                "installed_models": self.installed_models(), "loaded_models": self.loaded_models()}

    def ensure_ready(self, *, approve: frozenset = frozenset(), auto_pull: bool = True,
                     run_test: bool = True) -> dict[str, Any]:
        """Ortamı hazırla. Güvenli işler otomatik; SİLME/KURULUM onay ister (Madde 24). Donma önleme: test yalnız
        model GPU'ya sığıyorsa. `approve`: {'install_ollama','delete_model:<ad>','delete_unfit'}."""
        rep: dict[str, Any] = {"ready": False, "selected_model": None, "actions_executed": [],
                               "pending_approval": [], "test": None, "warnings": [], "message": ""}
        hw = self._hw.report()
        rep["gpu_available"] = hw["gpu_available"]
        rep["warnings"].extend(hw["warnings"])

        # 1) Ollama var mı / kurulu mu (kurulum = Madde 24 onay)
        if not self.ollama_reachable():
            if not self.ollama_installed():
                item = {"action": "install_ollama", "reason": "Ollama kurulu değil",
                        "command": self._install_command(), "requires_approval": True}
                if "install_ollama" in approve:
                    res = self._cli_install()
                    rep["actions_executed"].append({"action": "install_ollama", **res})
                    if not res.get("ok"):
                        rep["message"] = "Ollama kurulumu başarısız — komutu elle çalıştırın."
                        rep["pending_approval"].append(item)
                        return rep
                else:
                    rep["pending_approval"].append(item)
                    rep["message"] = "Ollama kurulu değil — kurulum ONAY ister (Madde 24)."
                    return rep
            else:
                rep["warnings"].append("Ollama kurulu ama çalışmıyor — 'ollama serve' başlatın.")
                rep["message"] = "Ollama çalışmıyor."
                return rep

        installed = self.installed_models()
        # 2) uygun modeli DETERMİNİSTİK seç (VRAM'e göre)
        rec = self._hw.recommend_model(installed or DEFAULT_CANDIDATES)
        selected = rec["recommended"]
        rep["selected_model"] = selected
        fits = any(c["model"] == selected and c["fits_gpu"] for c in rec.get("candidates", []))
        if rec.get("warning"):
            rep["warnings"].append("Uygun GPU modeli yok — CPU çıkarımı YAVAŞ; ağır test atlanır (donma önleme).")

        # 3) seçili model kurulu değilse indir (additive, güvenli)
        if selected and selected not in installed:
            if auto_pull:
                res = self.pull_model(selected)
                rep["actions_executed"].append({"action": "pull_model", "model": selected, "ok": res.get("ok")})
                if not res.get("ok"):
                    rep["warnings"].append(f"{selected} indirilemedi: {res.get('stderr') or res.get('error')}")
                    rep["message"] = "Model indirilemedi."
                    return rep
            else:
                rep["pending_approval"].append({"action": "pull_model", "model": selected,
                                                "requires_approval": False})

        # 4) VRAM boşalt: seçili OLMAYAN yüklü modelleri durdur (GÜVENLİ)
        base = (selected or "").split(":")[0]
        for m in self.loaded_models():
            nm = m.get("name", "")
            if nm and nm != selected and not nm.startswith(base):
                res = self.stop_model(nm)
                rep["actions_executed"].append({"action": "stop_model", "model": nm, "ok": res.get("ok")})

        # 5) sağlık+HIZ testi — YALNIZ GPU'ya sığıyorsa (donma önleme)
        if run_test and fits:
            t = self.test_model(selected)
            rep["test"] = t
            if t.get("ok") and t.get("placement") == "gpu" and t.get("fast"):
                rep["ready"] = True
                rep["message"] = (f"TEST BAŞARILI · Ollama bağlı · model={selected} · "
                                  f"{t['latency_ms']}ms · GPU")
            elif t.get("ok"):
                rep["warnings"].append(f"Model çalışıyor ama yerleşim={t.get('placement')} / "
                                       f"{t.get('latency_ms')}ms — beklenenden yavaş.")
                rep["ready"] = t.get("placement") == "gpu"
            else:
                rep["warnings"].append(f"Model testi başarısız: {t.get('error')}")
        else:
            rep["warnings"].append("Model GPU'ya sığmıyor ya da GPU yok → ağır test ATLANDI (donma önleme).")
            rep["message"] = rep["message"] or "Ortam CPU-çıkarımına uygun değil — küçük model/GPU gerekir."

        # 6) SİLME adayları (VRAM'e sığmayan kurulu modeller) → ÖNER (Madde 24; auto silmez)
        if installed:
            for c in self._hw.recommend_model(installed).get("candidates", []):
                if c["model"] != selected and not c["fits_gpu"]:
                    key = f"delete_model:{c['model']}"
                    if key in approve or "delete_unfit" in approve:
                        res = self.delete_model(c["model"], user_approved=True)
                        rep["actions_executed"].append({"action": "delete_model", "model": c["model"],
                                                        "ok": res.get("ok")})
                    else:
                        rep["pending_approval"].append({"action": "delete_model", "model": c["model"],
                                                        "reason": "VRAM'e sığmıyor (opsiyonel temizlik)",
                                                        "requires_approval": True})
        return rep

    def _cli_install(self) -> dict[str, Any]:
        """Onaylıysa Ollama kurulumunu dener (platforma göre). Başarısızsa elle komut önerilir."""
        import platform as _pf
        if _pf.system() == "Windows":
            return self._cli_raw(["winget", "install", "--id", "Ollama.Ollama", "-e", "--silent"])
        if _pf.system() == "Darwin":
            return self._cli_raw(["brew", "install", "ollama"])
        return {"ok": False, "error": "Otomatik kurulum yok — komutu elle çalıştırın", "manual": True}

    def _cli_raw(self, args: list) -> dict[str, Any]:
        try:
            p = self._runner(args, capture_output=True, text=True, timeout=1800)
            return {"ok": p.returncode == 0, "stderr": (p.stderr or "")[:400]}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:200]}


__all__ = ["LocalInferenceManager", "FAST_THRESHOLD_MS", "DEFAULT_CANDIDATES"]
