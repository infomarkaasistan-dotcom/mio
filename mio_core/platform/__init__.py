"""MIO Core · Platform — cross-cutting Production Hardening altyapısı (Domain DEĞİL).

Constitution: Madde 28 (Resilience & Graceful Degradation), Madde 27 (Observability). Bu paket bir bounded
context değil; tüm katmanlara hizmet eden, deterministik, stdlib-only dayanıklılık primitifleridir. Mevcut
Domain API'lerini/Capability sözleşmelerini değiştirmez — kenar katmanlara opt-in olarak uygulanır."""

from .resilience import (
    Backoff,
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    ResiliencePolicy,
    RetryExhaustedError,
    resilient_call,
)

__all__ = [
    "Backoff", "CircuitBreaker", "CircuitOpenError", "CircuitState", "ResiliencePolicy",
    "RetryExhaustedError", "resilient_call",
]
