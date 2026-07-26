"""MIO Core · Model Management Domain (Faz 5 · Domain 35) — üretim testleri: unit+integration+smoke.

Anayasa özü: **model seçimi DETERMİNİSTİK politikadır; LLM danışman, karar verici DEĞİL.** Placeholder/mock YOK;
gerçek SQLite + enjekte edilen deterministik provider üzerinden. Yaşam-döngüsü durum makinesi, deterministik
seçim, DÜRÜST no_connector (available olmaz), provider hatası görünür, Madde 24 retire onay kapısı doğrulanır."""

import pytest

from mio_core.domains.model_management import (
    Lifecycle,
    Location,
    Model,
    ModelEvents,
    ModelKind,
    ModelManagementDomain,
    ModelRepository,
    NotFoundError,
    TransitionError,
    UnauthorizedError,
    ValidationError,
    selection_score,
)
from mio_core.events import EventBus


def _build():
    repo = ModelRepository(":memory:")
    bus = EventBus(record=True)
    dom = ModelManagementDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def mm():
    return _build()


def _reg(d, actor="owner", **kw):
    name = kw.pop("name", "m")
    base = dict(kind=ModelKind.LLM, provider="ollama", location=Location.LOCAL,
                context_window=8192, cost_per_1k=0.0, priority=100)
    base.update(kw)
    return d.register_model(actor, name, **base)


# ---- UNIT: validation + authz + deterministik skor ----
def test_validation_authz_and_score(mm):
    d, _r, _b = mm
    with pytest.raises(UnauthorizedError):
        d.register_model("Reasoning", "x")           # reader ama writer değil
    with pytest.raises(ValidationError):
        d.register_model("owner", "x", kind="uydurma")
    with pytest.raises(ValidationError):
        d.register_model("owner", "x", location="uydurma")
    # deterministik skor: priority baskın, sonra context
    a = Model(name="a", priority=100, context_window=8000)
    b = Model(name="b", priority=200, context_window=4000)
    assert selection_score(b) > selection_score(a)   # yüksek priority kazanır


# ---- INTEGRATION: provision no_connector DÜRÜST → available OLMAZ ----
def test_provision_no_connector_stays_registered(mm):
    d, _r, bus = mm
    m = _reg(d, name="llama", provider="ollama")
    res = d.provision("owner", m["id"])
    assert res["provisioned"] is False and res["reason"] == "no_connector"
    assert res["status"] == Lifecycle.REGISTERED     # available OLMADI (dürüst)
    assert any(e["type"] == ModelEvents.NO_CONNECTOR for e in bus.history())
    # available olmadığı için seçim de None döner
    assert d.select("owner", ModelKind.LLM) is None


# ---- INTEGRATION: provider ile provision → available; provider hatası GÖRÜNÜR ----
def test_provision_success_and_failure_visible(mm):
    d, _r, bus = mm
    d.register_provider("ollama", lambda ctx: {"endpoint": "http://localhost:11434"}, name="ollama-adapter")
    m = _reg(d, name="llama", provider="ollama")
    ok = d.provision("owner", m["id"])
    assert ok["provisioned"] is True and ok["status"] == Lifecycle.AVAILABLE
    assert ok["model"]["endpoint"] == "http://localhost:11434"
    assert ok["model"]["connector"] == "ollama-adapter"
    # provider hatası → görünür (Madde 27), model registered kalır
    d.register_provider("badprov", lambda ctx: (_ for _ in ()).throw(RuntimeError("disk dolu")))
    m2 = _reg(d, name="broken", provider="badprov")
    fail = d.provision("owner", m2["id"])
    assert fail["provisioned"] is False and fail["reason"] == "failed" and "disk dolu" in fail["error"]
    assert fail["status"] == Lifecycle.REGISTERED
    assert any(e["type"] == ModelEvents.PROVISION_FAILED for e in bus.history())


# ---- INTEGRATION: DETERMİNİSTİK seçim politikası (LLM'siz) ----
def test_deterministic_selection(mm):
    d, _r, bus = mm
    d.register_provider("p", lambda ctx: {"endpoint": "x"})
    small = _reg(d, name="small", provider="p", priority=100, context_window=4096)
    big = _reg(d, name="big", provider="p", priority=100, context_window=32768)
    vip = _reg(d, name="vip", provider="p", priority=300, context_window=2048)
    for x in (small, big, vip):
        d.provision("owner", x["id"])
    # priority baskın → vip seçilir (context daha küçük olsa bile)
    chosen = d.select("owner", ModelKind.LLM)
    assert chosen["name"] == "vip"
    assert any(e["type"] == ModelEvents.MODEL_SELECTED for e in bus.history())
    # min_context kısıtı vip'i eler → context en büyük 'big' kazanır
    chosen2 = d.select("owner", ModelKind.LLM, min_context=8000)
    assert chosen2["name"] == "big"
    # deterministik: aynı girdi → aynı sonuç
    assert d.select("owner", ModelKind.LLM)["id"] == chosen["id"]
    # eşleşme yoksa None (uydurma YOK)
    assert d.select("owner", ModelKind.VISION) is None


# ---- INTEGRATION: yaşam-döngüsü durum makinesi + geçersiz geçiş ----
def test_lifecycle_transitions(mm):
    d, _r, _b = mm
    d.register_provider("p", lambda ctx: {"endpoint": "x"})
    m = _reg(d, name="m", provider="p")
    d.provision("owner", m["id"])                    # → available
    dep = d.deprecate("owner", m["id"])
    assert dep["status"] == Lifecycle.DEPRECATED
    assert d.select("owner", ModelKind.LLM) is None  # deprecated seçilemez
    react = d.reactivate("owner", m["id"])
    assert react["status"] == Lifecycle.AVAILABLE
    # geçersiz geçiş: REGISTERED → DEPRECATED doğrudan yapılamaz (durum makinesi korur)
    fresh = _reg(d, name="fresh", provider="p")      # REGISTERED
    with pytest.raises(TransitionError):
        d.deprecate("owner", fresh["id"])
    with pytest.raises(NotFoundError):
        d.get_model("owner", "yok-id")


# ---- INTEGRATION: retire Madde 24 onay kapısı ----
def test_retire_requires_approval(mm):
    d, _r, bus = mm
    d.register_provider("p", lambda ctx: {"endpoint": "x"})
    m = _reg(d, name="m", provider="p")
    d.provision("owner", m["id"])
    # writer ama approver değil → onay gerekir (retire edilmez)
    res = d.retire("Engineering", m["id"])
    assert res["retired"] is False and res["requires_approval"] is True
    assert res["status"] == Lifecycle.AVAILABLE
    assert any(e["type"] == ModelEvents.RETIRE_APPROVAL_REQUIRED for e in bus.history())
    # approver → emekli olur (terminal)
    done = d.retire("owner", m["id"])
    assert done["retired"] is True and done["status"] == Lifecycle.RETIRED
    assert any(e["type"] == ModelEvents.MODEL_RETIRED for e in bus.history())
    # emekli terminal: tekrar retire hata
    with pytest.raises(TransitionError):
        d.retire("owner", m["id"])


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(mm):
    d, _r, _b = mm
    d.register_provider("p", lambda ctx: {"endpoint": "x"})
    m = _reg(d, name="m", provider="p")
    d.provision("owner", m["id"])
    s = d.stats()
    assert s["models"] == 1 and s["available"] == 1 and s["providers"] == 1
    assert s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "model_management" and "select" in c["operations"]
    assert "deterministik" in c["selection_policy"]


# ---- SMOKE: boot() → deterministik seçim + no_connector dürüstlüğü uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    m = mio.model_management.register_model("owner", "yerel-llm", kind=ModelKind.LLM, provider="ollama",
                                            location=Location.LOCAL, context_window=8192, priority=200)
    # provider adapter bağlı değil → dürüst no_connector, available OLMAZ
    res = mio.model_management.provision("owner", m["id"])
    assert res["provisioned"] is False and res["reason"] == "no_connector"
    assert mio.model_management.select("owner", ModelKind.LLM) is None   # available yok
    # provider bağlanınca deterministik seçim çalışır
    mio.model_management.register_provider("ollama", lambda ctx: {"endpoint": "http://localhost:11434"})
    mio.model_management.provision("owner", m["id"])
    assert mio.model_management.select("owner", ModelKind.LLM)["name"] == "yerel-llm"
    assert mio.model_management.contract()["version"] == "1.0.0"
    mio.close()
