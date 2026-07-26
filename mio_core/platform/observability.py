"""MIO Core · Platform · Observability — structured logging + tracing (Production Hardening #4), stdlib-only.

Üç primitif, tümü DETERMİNİSTİK (enjekte edilebilir clock/id → test-deterministik), harici bağımlılık YOK:
- `StructuredFormatter`  : logging kayıtlarını tek-satır JSON'a çevirir (makine-okur log toplama için).
- `Tracer` / `Span`     : hafif, iç-içe (nested) span/trace primitifi — süre + tag + durum; correlation için trace_id.
- `redact_mapping`      : log/tag içindeki sır anahtarlarını maskeler (Güvenlik — .env sızıntısını önler).

Karar mercii Executive'dir; bunlar yalnız GÖZLEM katmanıdır (iş mantığı YOK)."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from uuid import uuid4

__all__ = [
    "StructuredFormatter", "Span", "Tracer", "redact_mapping", "SENSITIVE_KEY_MARKERS",
]

# Log/tag içinde maskelenecek sır anahtarı işaretleri (Güvenlik — asla sızdırma)
SENSITIVE_KEY_MARKERS = ("key", "token", "secret", "password", "passwd", "authorization", "api_key",
                         "apikey", "credential", "bearer")

_STD_LOGRECORD_FIELDS = frozenset(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


def redact_mapping(data: dict) -> dict:
    """Sözlükteki sır-benzeri anahtarların değerlerini maskeler (deterministik). İç içe sözlükleri de tarar."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        kl = str(k).lower()
        if any(m in kl for m in SENSITIVE_KEY_MARKERS):
            out[k] = "***redacted***"
        elif isinstance(v, dict):
            out[k] = redact_mapping(v)
        else:
            out[k] = v
    return out


class StructuredFormatter(logging.Formatter):
    """logging.Record → tek-satır JSON. `extra=` ile verilen alanlar dahil edilir; sırlar maskelenir."""

    def __init__(self, *, service: str = "mio", redact: bool = True) -> None:
        super().__init__()
        self._service = service
        self._redact = redact

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service,
            "message": record.getMessage(),
        }
        # extra= ile eklenen kullanıcı alanları (standart LogRecord alanları hariç)
        for k, v in record.__dict__.items():
            if k not in _STD_LOGRECORD_FIELDS and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)[:1000]
        if self._redact:
            payload = redact_mapping(payload)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_id: Optional[str] = None
    start: float = 0.0
    end: Optional[float] = None
    status: str = "ok"                       # ok | error
    tags: dict = field(default_factory=dict)

    def duration(self) -> Optional[float]:
        return None if self.end is None else (self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "trace_id": self.trace_id, "span_id": self.span_id,
                "parent_id": self.parent_id, "status": self.status,
                "duration": self.duration(), "tags": dict(self.tags)}


class Tracer:
    """Hafif iç-içe tracing. Enjekte edilebilir `clock`/`id_factory` → test-deterministik. Thread-güvenli DEĞİL
    (tek mantıksal akış için); correlation `trace_id` ile, nesting `parent_id` ile sağlanır."""

    def __init__(self, *, clock: Callable[[], float] = time.perf_counter,
                 id_factory: Optional[Callable[[], str]] = None) -> None:
        self._clock = clock
        self._id = id_factory or (lambda: uuid4().hex[:8])
        self._spans: list[Span] = []
        self._stack: list[Span] = []

    @contextmanager
    def span(self, name: str, **tags: Any):
        parent = self._stack[-1] if self._stack else None
        trace_id = parent.trace_id if parent is not None else self._id()
        sp = Span(name=name, trace_id=trace_id, span_id=self._id(),
                  parent_id=parent.span_id if parent is not None else None,
                  start=self._clock(), tags=dict(tags))
        self._stack.append(sp)
        try:
            yield sp
        except Exception as exc:  # noqa: BLE001 — span durumunu işaretle, hatayı yeniden fırlat
            sp.status = "error"
            sp.tags["error"] = str(exc)[:200]
            raise
        finally:
            sp.end = self._clock()
            self._stack.pop()
            self._spans.append(sp)

    def spans(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._spans]

    def trace(self, trace_id: str) -> list[dict[str, Any]]:
        """Belirli bir trace_id'ye ait tüm span'ler (correlation görünümü)."""
        return [s.to_dict() for s in self._spans if s.trace_id == trace_id]

    def reset(self) -> None:
        self._spans.clear()
        self._stack.clear()
