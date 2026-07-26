"""MIO Core · Planning Domain (Faz 1 · Domain 5) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite plan deposu + kararlı topolojik sıralama üzerinden. Validation,
authorization, bağımlılık sıralama determinizmi, döngü/dangling reddi, yetenek doğrulama, onay yetki ayrımı,
events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.capability import Capability, CapabilityRegistry
from mio_core.domains.planning import (
    InfeasiblePlanError,
    PlanEvents,
    PlanRepository,
    PlanStatus,
    PlanningDomain,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(with_caps=False):
    caps = None
    if with_caps:
        caps = CapabilityRegistry()
        caps.register(Capability(name="send_email", description="e-posta gönder"))
    bus = EventBus(record=True)
    dom = PlanningDomain(PlanRepository(":memory:"), capabilities=caps, bus=bus)
    return dom, bus


@pytest.fixture
def pd():
    return _build()


def _linear_plan(d, actor="owner"):
    """A → B → C (C, B'ye; B, A'ya bağımlı)."""
    p = d.draft_plan(actor, "gelir hedefine ulaş")
    a = d.add_step(actor, p["id"], "A: pazar analizi")
    b = d.add_step(actor, p["id"], "B: içerik üret", requires=[a["id"]])
    c = d.add_step(actor, p["id"], "C: yayınla", requires=[b["id"]])
    return p, a, b, c


# ---- UNIT: validation ----
def test_draft_and_step_validation(pd):
    d, _b = pd
    with pytest.raises(ValidationError):
        d.draft_plan("owner", "   ")                       # boş amaç
    p = d.draft_plan("owner", "amaç")
    with pytest.raises(ValidationError):
        d.add_step("owner", p["id"], "  ")                 # boş adım
    with pytest.raises(ValidationError):
        d.add_step("owner", p["id"], "X", requires=["yok-id"])  # bilinmeyen bağımlılık
    with pytest.raises(NotFoundError):
        d.plan_view("owner", "yok-plan")


# ---- UNIT: authorization ----
def test_authorization(pd):
    d, _b = pd
    with pytest.raises(UnauthorizedError):
        d.draft_plan("yabanci", "amaç")
    p = d.draft_plan("owner", "amaç")
    with pytest.raises(UnauthorizedError):
        d.mark_approved("Planning", p["id"])               # onay yalnız Executive/owner


# ---- INTEGRATION: deterministik sıralama ----
def test_sequence_is_deterministic_topological(pd):
    d, bus = pd
    p, a, b, c = _linear_plan(d)
    out = d.sequence("owner", p["id"])
    ids = [s["id"] for s in out["ordered_steps"]]
    assert ids == [a["id"], b["id"], c["id"]]              # bağımlılık sırası
    assert out["status"] == PlanStatus.SEQUENCED
    assert [s["order"] for s in out["ordered_steps"]] == [0, 1, 2]
    again = d.sequence("owner", p["id"])                   # idempotent/deterministik
    assert [s["id"] for s in again["ordered_steps"]] == ids
    assert any(e["type"] == PlanEvents.SEQUENCED for e in bus.history())


def test_sequence_detects_cycle():
    # add_step yalnız MEVCUT adımlara bağımlılığa izin verir (ileri döngü kurulamaz — bu bir güvencedir).
    # Döngüyü doğrulamak için karşılıklı-bağımlı iki adımı doğrudan modelden kurup depoya yazıyoruz.
    from mio_core.domains.planning.models import Plan, PlanStep
    d, _b = _build()
    s1 = PlanStep(description="S1")
    s2 = PlanStep(description="S2", requires=[s1.id])
    s1.requires = [s2.id]                                  # S1↔S2 karşılıklı → döngü
    plan = Plan(objective="cyclic", steps=[s1, s2])
    d._repo.put(plan)
    with pytest.raises(InfeasiblePlanError):
        d.sequence("owner", plan.id)


# ---- INTEGRATION: assess fizibilite + yetenek doğrulama ----
def test_assess_feasible_and_capability_check():
    d, _b = _build(with_caps=True)
    p = d.draft_plan("owner", "kampanya")
    a = d.add_step("owner", p["id"], "listeyi hazırla")
    d.add_step("owner", p["id"], "gönder", requires=[a["id"]], capability="send_email")
    ok = d.assess("owner", p["id"])
    assert ok["feasible"] is True and ok["issues"] == []
    assert ok["capability_coverage"] == 0.5 and ok["missing_capabilities"] == []
    # bilinmeyen yetenek → fizibil değil
    d.add_step("owner", p["id"], "sms at", capability="send_sms")
    bad = d.assess("owner", p["id"])
    assert bad["feasible"] is False and "send_sms" in bad["missing_capabilities"]


# ---- INTEGRATION: onay yaşam-döngüsü (yetki ayrımı) ----
def test_approval_lifecycle():
    d, bus = _build()
    p, _a, _b, _c = _linear_plan(d)
    with pytest.raises(ValidationError):
        d.mark_approved("owner", p["id"])                  # önce sequence gerekir
    d.sequence("owner", p["id"])
    approved = d.mark_approved("Executive", p["id"])       # Executive onaylar
    assert approved["status"] == PlanStatus.APPROVED
    assert any(e["type"] == PlanEvents.APPROVED for e in bus.history())


def test_abandon_blocks_mutation(pd):
    d, _b = pd
    p = d.draft_plan("owner", "amaç")
    d.abandon("owner", p["id"])
    assert d.plan_view("owner", p["id"])["status"] == PlanStatus.ABANDONED
    with pytest.raises(ValidationError):
        d.add_step("owner", p["id"], "yeni adım")          # terk edilmiş plan değişmez


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(pd):
    d, _b = pd
    p, *_ = _linear_plan(d)
    d.sequence("owner", p["id"])
    s = d.stats()
    assert s["total"] >= 1 and s["sequenced"] >= 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "planning" and c["version"] == "1.0.0" and "sequence" in c["operations"]


# ---- SMOKE: boot() → domain uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    p = mio.planning.draft_plan("owner", "aylık gelir planı")
    a = mio.planning.add_step("owner", p["id"], "landing page hazırla")
    mio.planning.add_step("owner", p["id"], "reklam yayınla", requires=[a["id"]])
    out = mio.planning.sequence("owner", p["id"])
    assert [s["order"] for s in out["ordered_steps"]] == [0, 1]
    rep = mio.planning.assess("owner", p["id"])
    assert rep["feasible"] is True
    mio.planning.mark_approved("owner", p["id"])
    assert mio.planning.plan_view("owner", p["id"])["status"] == PlanStatus.APPROVED
    assert mio.planning.contract()["version"] == "1.0.0"
    mio.close()
