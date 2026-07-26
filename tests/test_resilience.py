"""MIO Core · Platform Resilience (Production Hardening · DEBT-002/003) — üretim testleri.

Placeholder/mock YOK; gerçek primitifler + gerçek ToolOrchestrator + gerçek EventBus üzerinden.
Deterministik (enjekte edilen clock/sleeper). Retry/backoff/circuit-breaker/graceful-degradation ve
EventBus sessiz-hata görünürlüğü (Madde 27/28) doğrulanır. Backward-compat korunur (policy yoksa eski davranış)."""

import pytest

from mio_core.capability import Capability, CapabilityRegistry
from mio_core.events import EventBus
from mio_core.execution.orchestrator import ToolOrchestrator, ToolRequest
from mio_core.platform.resilience import (
    Backoff,
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    ResiliencePolicy,
    RetryExhaustedError,
    resilient_call,
)


# ---- UNIT: Backoff ----
def test_exponential_backoff_deterministic():
    b = Backoff(base=0.1, factor=2.0, max_delay=1.0, jitter=0.0)
    assert b.delay(1) == 0.1 and b.delay(2) == 0.2 and b.delay(3) == 0.4
    assert b.delay(10) == 1.0                              # max_delay tavanı


# ---- UNIT: CircuitBreaker (fake clock) ----
def test_circuit_breaker_state_machine():
    now = [1000.0]
    br = CircuitBreaker(failure_threshold=2, reset_timeout=30.0, clock=lambda: now[0])
    assert br.allow() is True and br.state == CircuitState.CLOSED
    br.on_failure(); assert br.state == CircuitState.CLOSED   # 1 < eşik
    br.on_failure()                                          # 2 == eşik → AÇILIR
    assert br.state == CircuitState.OPEN and br.allow() is False
    now[0] += 31.0                                           # reset_timeout geçti
    assert br.state == CircuitState.HALF_OPEN and br.allow() is True   # tek deneme
    assert br.allow() is False                              # half-open ikinci deneme yok
    br.on_success(); assert br.state == CircuitState.CLOSED  # başarı → kapanır


def test_circuit_half_open_failure_reopens():
    now = [0.0]
    br = CircuitBreaker(failure_threshold=1, reset_timeout=10.0, clock=lambda: now[0])
    br.on_failure(); assert br.state == CircuitState.OPEN
    now[0] += 11.0
    assert br.allow() is True                               # half-open denemesi
    br.on_failure(); assert br.state == CircuitState.OPEN   # half-open'da hata → tekrar açılır


# ---- UNIT: resilient_call ----
def test_resilient_call_retries_then_succeeds():
    slept = []
    pol = ResiliencePolicy(retries=2, backoff=Backoff(base=0.1, jitter=0.0), sleeper=slept.append)
    calls = {"n": 0}
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("geçici")
        return "ok"
    assert resilient_call(flaky, policy=pol) == "ok"
    assert calls["n"] == 3 and slept == [0.1, 0.2]          # 2 backoff (deterministik)


def test_resilient_call_exhausts():
    pol = ResiliencePolicy(retries=1, backoff=Backoff(base=0.0), sleeper=lambda d: None)
    with pytest.raises(RetryExhaustedError):
        resilient_call(lambda: (_ for _ in ()).throw(RuntimeError("hep hata")), policy=pol)


def test_resilient_call_circuit_open_and_retry_on():
    br = CircuitBreaker(failure_threshold=1)
    br.on_failure()                                         # açık
    with pytest.raises(CircuitOpenError):
        resilient_call(lambda: "x", breaker=br)
    # retry_on False → orijinal hata hemen yükselir (yeniden-deneme yok)
    pol = ResiliencePolicy(retries=3, sleeper=lambda d: None)
    with pytest.raises(ValueError):
        resilient_call(lambda: (_ for _ in ()).throw(ValueError("kalıcı")),
                       policy=pol, retry_on=lambda e: not isinstance(e, ValueError))


# ---- INTEGRATION: orchestrator + policy (circuit breaker + backoff) ----
class _AlwaysFail:
    def __init__(self): self.calls = 0
    def execute(self, cap, action, args):
        self.calls += 1
        raise RuntimeError("bağımlılık düştü")


def _orch_with_policy(threshold=2):
    now = [0.0]
    slept = []
    caps = CapabilityRegistry()
    caps.register(Capability(name="flaky", connected=True))
    pol = ResiliencePolicy(retries=1, backoff=Backoff(base=0.1, jitter=0.0),
                           failure_threshold=threshold, reset_timeout=30.0,
                           sleeper=slept.append, clock=lambda: now[0])
    orch = ToolOrchestrator(caps, resilience=pol)
    ex = _AlwaysFail()
    orch.register_executor("flaky", ex)
    return orch, ex, now, slept


def test_orchestrator_circuit_opens_and_protects():
    orch, ex, now, slept = _orch_with_policy(threshold=2)
    r1 = orch.execute(ToolRequest("flaky", "run"))
    assert r1.success is False and r1.attempts == 2 and slept == [0.1]   # 1 backoff/çağrı
    orch.execute(ToolRequest("flaky", "run"))              # 2. başarısızlık → devre açılır
    assert orch.circuit_state("flaky") == CircuitState.OPEN
    calls_before = ex.calls
    r3 = orch.execute(ToolRequest("flaky", "run"))         # devre açık → yürütücü ÇAĞRILMAZ
    assert r3.error == "circuit_open" and ex.calls == calls_before      # graceful degradation
    now[0] += 31.0                                          # reset → half-open (tek mantıksal deneme)
    orch.execute(ToolRequest("flaky", "run"))
    assert ex.calls == calls_before + 2                    # 1 mantıksal çağrı = retries+1 deneme
    assert orch.circuit_state("flaky") == CircuitState.OPEN  # half-open'da hata → devre tekrar açıldı


def test_orchestrator_without_policy_is_backward_compatible():
    caps = CapabilityRegistry()
    caps.register(Capability(name="flaky", connected=True))
    orch = ToolOrchestrator(caps)                          # policy YOK → tarihsel davranış
    ex = _AlwaysFail()
    orch.register_executor("flaky", ex)
    r = orch.execute(ToolRequest("flaky", "run"))
    assert r.success is False and r.attempts == 2 and orch.circuit_state("flaky") == CircuitState.CLOSED


# ---- INTEGRATION: EventBus sessiz-hata görünürlüğü (Madde 27) ----
def test_eventbus_surfaces_subscriber_errors():
    bus = EventBus(record=True)
    def boom(_ev):
        raise RuntimeError("abone patladı")
    bus.subscribe("x.happened", boom)
    bus.publish("x.happened", {"a": 1})                    # publish PATLAMAZ
    errs = bus.subscriber_errors()
    assert errs["dropped"] == 1 and errs["recent"][0]["type"] == "x.happened"


def test_eventbus_error_handler_hook():
    seen = []
    bus = EventBus()
    bus.set_error_handler(lambda ev, h, exc: seen.append((ev["type"], str(exc))))
    bus.subscribe_all(lambda _ev: (_ for _ in ()).throw(ValueError("x")))
    bus.publish("y.z")
    assert seen and seen[0][0] == "y.z"


# ---- SMOKE: boot() → resilience bağlı + bus hataları observability'ye akıyor ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    # orchestrator resilience policy ile kuruldu; devre durumu sorgulanabilir (gözlemlenebilirlik)
    assert mio.orchestrator.circuit_state("herhangi") == CircuitState.CLOSED
    # bus abone hatası → observability sayacı (sessiz değil)
    mio.bus.subscribe("probe.evt", lambda _ev: (_ for _ in ()).throw(RuntimeError("kasıtlı")))
    mio.bus.publish("probe.evt", {})
    assert mio.bus.subscriber_errors()["dropped"] >= 1
    snap = mio.observability_domain.snapshot("owner")
    assert snap["metrics"].get("platform.bus_subscriber_errors", 0) >= 1
    mio.close()
