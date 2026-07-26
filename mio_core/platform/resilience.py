"""MIO Core · Platform · Resilience — dayanıklılık primitifleri (Madde 28), stdlib-only, DETERMİNİSTİK.

Retry · Exponential Backoff · Circuit Breaker · Graceful Degradation. Tümü enjekte edilebilir saat (`clock`)
ve uyutucu (`sleeper`) ile test-deterministiktir (gerçek `time` yalnız üretim varsayılanıdır). Karar mercii
hâlâ Executive'dir; bunlar yalnız 'nasıl güvenli çağırırım' katmanıdır."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("mio.platform.resilience")

__all__ = [
    "Backoff", "CircuitState", "CircuitBreaker", "CircuitOpenError", "RetryExhaustedError",
    "ResiliencePolicy", "resilient_call",
]


class CircuitOpenError(Exception):
    """Devre açık — bağımlılık geçici olarak korunuyor (çağrı yapılmadı)."""


class RetryExhaustedError(Exception):
    """Tüm denemeler tükendi."""
    def __init__(self, attempts: int, last_error: str) -> None:
        super().__init__(f"{attempts} deneme başarısız: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


@dataclass
class Backoff:
    """Üstel geri-çekilme. jitter=0 → tam deterministik (test)."""
    base: float = 0.1
    factor: float = 2.0
    max_delay: float = 30.0
    jitter: float = 0.0                      # 0..1 oran; üretimde thundering-herd'i kırar

    def delay(self, attempt: int) -> float:
        """attempt 1-tabanlı; ilk yeniden-denemeden önceki gecikme delay(1)."""
        d = min(self.max_delay, self.base * (self.factor ** max(0, attempt - 1)))
        if self.jitter > 0 and d > 0:
            import random
            d += random.uniform(0.0, self.jitter * d)
        return d


class CircuitState:
    CLOSED = "closed"          # normal
    OPEN = "open"              # bağımlılık başarısız → çağrılar kısa-devre
    HALF_OPEN = "half_open"    # deneme penceresi (bir çağrıya izin ver)


class CircuitBreaker:
    """Deterministik devre kesici. Ardışık başarısızlık eşiği aşınca AÇILIR; reset_timeout sonra HALF_OPEN
    olur ve tek deneme başarılıysa KAPANIR. Enjekte edilebilir `clock` ile test-deterministik."""

    def __init__(self, *, failure_threshold: int = 5, reset_timeout: float = 30.0,
                 half_open_max: int = 1, clock: Callable[[], float] = time.monotonic) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.reset_timeout = max(0.0, reset_timeout)
        self.half_open_max = max(1, half_open_max)
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        # OPEN → reset_timeout dolduysa HALF_OPEN'a geçir (lazy)
        if self._state == CircuitState.OPEN and self._clock() - self._opened_at >= self.reset_timeout:
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0
        return self._state

    def allow(self) -> bool:
        """Şu an bir çağrıya izin var mı?"""
        st = self.state
        if st == CircuitState.CLOSED:
            return True
        if st == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max:
                self._half_open_calls += 1
                return True
            return False
        return False  # OPEN

    def on_success(self) -> None:
        self._failures = 0
        self._half_open_calls = 0
        self._state = CircuitState.CLOSED

    def on_failure(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._trip()
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()
        self._half_open_calls = 0

    def snapshot(self) -> dict[str, Any]:
        return {"state": self.state, "failures": self._failures,
                "failure_threshold": self.failure_threshold}


@dataclass
class ResiliencePolicy:
    """Retry + Backoff + Circuit Breaker demeti. Enjekte edilebilir sleeper/clock → deterministik test."""
    retries: int = 1                          # ek deneme sayısı (toplam = retries+1)
    backoff: Backoff = field(default_factory=Backoff)
    failure_threshold: int = 5
    reset_timeout: float = 30.0
    sleeper: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic

    def new_breaker(self) -> CircuitBreaker:
        return CircuitBreaker(failure_threshold=self.failure_threshold,
                              reset_timeout=self.reset_timeout, clock=self.clock)


def resilient_call(fn: Callable[[], Any], *, policy: Optional[ResiliencePolicy] = None,
                   breaker: Optional[CircuitBreaker] = None,
                   retry_on: Callable[[Exception], bool] = lambda e: True,
                   on_retry: Optional[Callable[[int, Exception], None]] = None) -> Any:
    """`fn`'i policy'ye göre güvenli çağırır. Devre açıksa `CircuitOpenError`; denemeler tükenirse
    `RetryExhaustedError`. Karar/iş mantığı burada YOK — yalnız güvenli çağrı orkestrasyonu."""
    policy = policy or ResiliencePolicy()
    if breaker is not None and not breaker.allow():
        raise CircuitOpenError("Devre açık — çağrı yapılmadı")
    attempts, last_exc = 0, None
    for i in range(policy.retries + 1):
        attempts += 1
        try:
            result = fn()
            if breaker is not None:
                breaker.on_success()
            return result
        except Exception as exc:  # noqa: BLE001 — resilience sınırı; kontrollü yeniden-deneme
            last_exc = exc
            if not retry_on(exc):
                if breaker is not None:
                    breaker.on_failure()
                raise
            if i < policy.retries:
                if on_retry is not None:
                    on_retry(attempts, exc)
                delay = policy.backoff.delay(attempts)
                if delay > 0:
                    policy.sleeper(delay)
    if breaker is not None:
        breaker.on_failure()
    raise RetryExhaustedError(attempts, str(last_exc)[:300])
