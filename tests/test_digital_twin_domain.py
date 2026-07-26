"""MIO Core · Simulation & Digital Twin Domain (Faz 5 · Domain 42) — üretim testleri: unit+integration+smoke.

Anayasa özü: **SİMÜLASYON ≠ GERÇEKLİK; sonuç ÖNERİDİR, yansıtma Madde 24 onayı ister.** Placeholder/mock YOK;
gerçek SQLite + dahili deterministik simülatör (+ opsiyonel enjekte dış simülatör). Deterministik what-if,
simulate() ikizi mutate ETMEZ, Madde 24 yansıtma, DÜRÜST no_simulator, sim hatası, events doğrulanır."""

import pytest

from mio_core.domains.digital_twin import (
    DigitalTwinDomain,
    DigitalTwinEvents,
    DigitalTwinRepository,
    NotFoundError,
    SimStatus,
    UnauthorizedError,
    ValidationError,
    apply_step,
)
from mio_core.events import EventBus


def _build():
    repo = DigitalTwinRepository(":memory:")
    bus = EventBus(record=True)
    dom = DigitalTwinDomain(repo, bus=bus)
    return dom, repo, bus


@pytest.fixture
def dt():
    return _build()


# ---- UNIT: apply_step deterministik + validation + authz ----
def test_apply_step_and_authz(dt):
    d, _r, _b = dt
    st, tr = apply_step({"x": 10}, {"op": "inc", "var": "x", "value": 5})
    assert st["x"] == 15.0 and tr["before"] == 10 and tr["after"] == 15.0
    st2, _ = apply_step({"x": 10}, {"op": "mul", "var": "x", "value": 3})
    assert st2["x"] == 30.0
    with pytest.raises(ValidationError):
        apply_step({}, {"op": "uydurma", "var": "x", "value": 1})
    with pytest.raises(UnauthorizedError):
        d.register_twin("Perception", "t")                    # reader ama writer değil


# ---- INTEGRATION: simulate DETERMİNİSTİK + ikizi MUTATE ETMEZ (sim ≠ gerçeklik) ----
def test_simulate_is_deterministic_and_non_mutating(dt):
    d, _r, bus = dt
    twin = d.register_twin("owner", "Depo", state={"stok": 100.0, "sıcaklık": 20.0})
    steps = [{"op": "dec", "var": "stok", "value": 30}, {"op": "inc", "var": "sıcaklık", "value": 4}]
    run = d.simulate("owner", twin["id"], steps, scenario="talep artışı")
    assert run["status"] == SimStatus.COMPLETED
    assert run["final_state"]["stok"] == 70.0 and run["final_state"]["sıcaklık"] == 24.0
    assert run["simulator"] == "internal" and len(run["trace"]) == 2
    # KRİTİK: ikiz gerçek durumu DEĞİŞMEDİ (sim ≠ gerçeklik)
    fresh = d.get_twin("owner", twin["id"])
    assert fresh["state"] == {"stok": 100.0, "sıcaklık": 20.0}
    # deterministik: aynı girdi → aynı çıktı
    run2 = d.simulate("owner", twin["id"], steps)
    assert run2["final_state"] == run["final_state"]
    assert any(e["type"] == DigitalTwinEvents.SIMULATED for e in bus.history())


# ---- INTEGRATION: sonucu ikize yansıtma Madde 24 onayı ister ----
def test_apply_result_requires_approval(dt):
    d, _r, bus = dt
    twin = d.register_twin("owner", "Hat", state={"hız": 5.0})
    run = d.simulate("owner", twin["id"], [{"op": "set", "var": "hız", "value": 9.0}])
    with pytest.raises(UnauthorizedError):
        d.apply_result("Engineering", run["id"])              # approver değil
    res = d.apply_result("owner", run["id"])                  # owner onaylar → ikize yansır
    assert res["applied"] is True and res["twin"]["state"]["hız"] == 9.0
    assert res["run"]["applied_by"] == "owner"
    assert any(e["type"] == DigitalTwinEvents.RESULT_APPLIED for e in bus.history())
    # ikiz artık gerçekten güncellendi
    assert d.get_twin("owner", twin["id"])["state"]["hız"] == 9.0
    # ikinci kez yansıtılamaz
    with pytest.raises(ValidationError):
        d.apply_result("owner", run["id"])


# ---- INTEGRATION: dış fiziksel model gerekli ama adapter yok → DÜRÜST no_simulator ----
def test_no_simulator_when_external_required(dt):
    d, _r, bus = dt
    twin = d.register_twin("owner", "Reaktör", kind="thermal", state={"t": 300.0},
                           requires_external_sim=True)
    run = d.simulate("owner", twin["id"], [{"op": "inc", "var": "t", "value": 50}])
    assert run["status"] == SimStatus.NO_SIMULATOR and run["final_state"] == {}
    assert any(e["type"] == DigitalTwinEvents.NO_SIMULATOR for e in bus.history())
    # yansıtma yalnız completed için
    with pytest.raises(ValidationError):
        d.apply_result("owner", run["id"])


# ---- INTEGRATION: dış simülatör adapter ile delege ----
def test_external_simulator_delegation(dt):
    d, _r, _b = dt
    twin = d.register_twin("owner", "Akış", kind="fluid", state={"p": 1.0}, requires_external_sim=True)
    d.register_simulator("fluid", lambda ctx: {"final_state": {"p": 2.5}, "trace": [{"solver": "cfd"}]},
                         name="cfd-engine")
    run = d.simulate("owner", twin["id"], [{"op": "inc", "var": "p", "value": 1}])
    assert run["status"] == SimStatus.COMPLETED and run["final_state"]["p"] == 2.5
    assert run["simulator"] == "cfd-engine"


# ---- INTEGRATION: geçersiz adım → ValidationError; sim hatası → failed ----
def test_invalid_step_and_sim_failure(dt):
    d, _r, bus = dt
    twin = d.register_twin("owner", "T", state={"x": 1.0})
    with pytest.raises(ValidationError):
        d.simulate("owner", twin["id"], [{"op": "inc", "var": "x", "value": "sayı-değil"}])
    # dış simülatör hatası → failed (görünür)
    ext = d.register_twin("owner", "E", kind="k", requires_external_sim=True)
    d.register_simulator("k", lambda ctx: (_ for _ in ()).throw(RuntimeError("çözücü çöktü")))
    run = d.simulate("owner", ext["id"], [{"op": "set", "var": "y", "value": 1}])
    assert run["status"] == SimStatus.FAILED and "çözücü çöktü" in run["error"]
    assert any(e["type"] == DigitalTwinEvents.SIM_FAILED for e in bus.history())


# ---- INTEGRATION: list + stats + contract ----
def test_list_stats_contract(dt):
    d, _r, _b = dt
    twin = d.register_twin("owner", "T", state={"a": 0.0})
    d.simulate("owner", twin["id"], [{"op": "inc", "var": "a", "value": 1}])
    assert len(d.list_twins("owner")) == 1
    assert len(d.list_runs("owner", twin_id=twin["id"])) == 1
    s = d.stats()
    assert s["twins"] == 1 and s["runs"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "digital_twin" and "apply_result" in c["operations"]
    with pytest.raises(NotFoundError):
        d.get_twin("owner", "yok")


# ---- SMOKE: boot() → what-if + sim≠gerçeklik + Madde 24 uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    tw = mio.digital_twin.register_twin("owner", "Fabrika", state={"üretim": 1000.0})
    run = mio.digital_twin.simulate("owner", tw["id"], [{"op": "mul", "var": "üretim", "value": 1.2}])
    assert run["final_state"]["üretim"] == 1200.0
    # sim ≠ gerçeklik: ikiz hâlâ 1000 (onaysız yansımaz)
    assert mio.digital_twin.get_twin("owner", tw["id"])["state"]["üretim"] == 1000.0
    mio.digital_twin.apply_result("owner", run["id"])         # Madde 24 onayı → yansır
    assert mio.digital_twin.get_twin("owner", tw["id"])["state"]["üretim"] == 1200.0
    assert mio.digital_twin.contract()["version"] == "1.0.0"
    mio.close()
