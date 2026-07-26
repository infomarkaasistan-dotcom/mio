"""MIO Core · Platform · Config — TEK yapılandırma kaynağı (.env + os.environ), stdlib-only.

**Kök neden düzeltmesi:** Önceki durumda `.env` dosyası HİÇBİR yerde yüklenmiyordu; `register_from_env` yalnız
`os.environ`'a bakıyordu → `.env`'deki `LLM_ENABLED=true` runtime'a ULAŞMIYORDU. Bu modül `.env`'i stdlib ile
parse eder ve tek bir `Config` nesnesinde birleştirir. **Tüm arayüzler (CLI/HTTP/Dashboard/Mobile) AYNI Config
instance'ını tüketir** (Interface Architecture). Harici bağımlılık YOK (python-dotenv kullanılmaz — Anayasa).

Öncelik (yüksekten düşüğe): explicit overrides > gerçek `os.environ` > `.env` dosyası > default.
(Standart dotenv semantiği: gerçek ortam değişkeni `.env`'i override eder — deployment kontrolü. Ama env'de
değişken YOKSA `.env` değeri kullanılır → kullanıcının `.env`'e yazdığı değer etkili olur.)"""

from __future__ import annotations

import os
from typing import Any, Optional

_TRUE = ("1", "true", "yes", "on")
_FALSE = ("0", "false", "no", "off", "")


def load_env_file(path: str) -> dict[str, str]:
    """`.env` dosyasını parse eder (KEY=VALUE). Yorum (#) ve boş satır atlanır; tırnaklar soyulur; `export`
    öneki kabul edilir. Dosya yoksa boş sözlük (dürüst — çökme yok)."""
    out: dict[str, str] = {}
    if not path or not os.path.exists(path):
        return out
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.lower().startswith("export "):
                    line = line[7:].lstrip()
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
                    val = val[1:-1]                     # tırnaklı değer
                if key:
                    out[key] = val
    except Exception:  # noqa: BLE001 — bozuk .env → boş (dürüst), runtime çökmez
        return out
    return out


class Config:
    """Tek yapılandırma nesnesi. `.env` + `os.environ` + overrides birleşimi (öncelik: overrides > env > .env)."""

    def __init__(self, *, env_file: Optional[str] = ".env", environ: Optional[dict] = None,
                 overrides: Optional[dict] = None) -> None:
        self.env_file = env_file
        self._file = load_env_file(env_file) if env_file else {}
        self._environ = dict(os.environ if environ is None else environ)
        self._overrides = dict(overrides or {})

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._overrides:
            return self._overrides[key]
        if key in self._environ:
            return self._environ[key]
        return self._file.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        v = self.get(key, None)
        if v is None:
            return default
        s = str(v).strip().lower()
        if s in _TRUE:
            return True
        if s in _FALSE:
            return False
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(str(self.get(key, default)).strip())
        except (TypeError, ValueError):
            return default

    def has(self, key: str) -> bool:
        return key in self._overrides or key in self._environ or key in self._file

    def source_of(self, key: str) -> str:
        """Bir değerin nereden geldiği (teşhis için): overrides | environ | env_file | absent."""
        if key in self._overrides:
            return "overrides"
        if key in self._environ:
            return "environ"
        if key in self._file:
            return "env_file"
        return "absent"

    def as_dict(self) -> dict[str, str]:
        """Birleşik görünüm (register_from_env vb. için). Öncelik uygulanmış tek sözlük."""
        merged: dict[str, str] = {}
        merged.update(self._file)
        merged.update({k: v for k, v in self._environ.items()})
        merged.update({k: str(v) for k, v in self._overrides.items()})
        return merged

    def diagnostics(self) -> dict[str, Any]:
        """Yapılandırma teşhisi (SIR DEĞERLERİ maskeli): hangi anahtar nereden geliyor."""
        from mio_core.platform.observability import SENSITIVE_KEY_MARKERS
        keys = set(self._file) | set(self._overrides) | {
            k for k in self._environ if k.startswith("MIO_") or k in
            ("LLM_ENABLED", "OLLAMA_HOST", "SMTP_HOST", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "QWEN_API_KEY")}
        rows = {}
        for k in sorted(keys):
            src = self.source_of(k)
            val = self.get(k)
            if any(m in k.lower() for m in SENSITIVE_KEY_MARKERS):
                val = "***redacted***" if val else ""
            rows[k] = {"value": val, "source": src}
        return {"env_file": self.env_file, "env_file_loaded": bool(self._file), "keys": rows}


__all__ = ["Config", "load_env_file"]
