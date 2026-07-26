"""MIO Core · Born Capable (ADR-0001/0002) — üretim testleri (deterministik, LLM-siz).

Purpose Layer + Capability Registry (semantik) + Brain Registry (14 doğuştan) + Self Awareness Layer +
born.birth() bütünü. MIO'nun boş değil, YETENEKLİ doğduğunu doğrular.
"""

import pytest

from mio_core.born import birth, default_capabilities, default_innate_beliefs, default_purpose
from mio_core.brains import BrainRegistry, default_domain_brains
from mio_core.capability import Capability, CapabilityRegistry, RiskLevel
from mio_core.executive import ExecutiveState, SQLiteBeliefStore, SQLiteExecutiveStateStore
from mio_core.executive.cognitive import CognitiveEngine
from mio_core.self_awareness import SelfAwareness


@pytest.fixture
def state(tmp_path):
    s = SQLiteExecutiveStateStore(str(tmp_path / "exec.db"))
    yield ExecutiveState(s)
    s.close()


# ---- Purpose Layer (E1) ----
def test_purpose_seeded_once_and_versioned(state):
    p = state.ensure_purpose(default_purpose())
    assert "sürdürülebilir gelir" in p.primary_objective.lower()
    assert p.financial_rule and p.version == 1
    # ikinci kez ensure → mevcut döner (yeni doğuş yok)
    again = state.ensure_purpose(default_purpose())
    assert again.version == 1
    # açık güncelleme → sürüm artar
    p2 = state.set_purpose(default_purpose())
    assert p2.version == 2


# ---- Capability Registry (semantik) ----
def test_capability_semantics_and_connection():
    reg = CapabilityRegistry()
    reg.register_all(default_capabilities())
    pay = reg.get("payment")
    assert pay.requires_user_approval and pay.incurs_cost and pay.risk_level == RiskLevel.HIGH
    # doğuşta hiçbiri bağlı değil (keşfedilmedi) — dürüst
    assert reg.list_connected() == []
    reg.set_connected("filesystem", True)
    assert reg.can("filesystem") and not reg.can("payment")
    assert [c.name for c in reg.list_connected()] == ["filesystem"]


def test_capability_usable_by_brain():
    reg = CapabilityRegistry()
    reg.register(Capability("git", usable_by_brains=["Engineering"], connected=True))
    reg.register(Capability("filesystem", connected=True))          # ["*"]
    eng = {c.name for c in reg.list_for_brain("Engineering")}
    fin = {c.name for c in reg.list_for_brain("Finance")}
    assert "git" in eng and "filesystem" in eng
    assert "git" not in fin and "filesystem" in fin                # "*" herkese, git yalnız Engineering


# ---- Brain Registry (14 doğuştan) ----
def test_default_brains_born_in():
    brains = default_domain_brains()
    names = {b.name for b in brains}
    assert len(brains) == 14
    for expected in ("Executive", "Finance", "Marketing", "Engineering", "Security",
                     "Learning", "Identity", "Workflow"):
        assert expected in names
    execb = next(b for b in brains if b.name == "Executive")
    assert execb.capabilities == ["*"] and "Decision Science" in execb.knowledge_domains


# ---- born.birth() bütünü ----
def test_birth_assembles_capable_mio(state):
    cog = SQLiteBeliefStore(":memory:")
    engine = CognitiveEngine(cog)
    brains = BrainRegistry()
    caps = CapabilityRegistry()
    summary = birth(state, brains, caps, cognitive=engine)
    assert summary["identity"] == "MIO"
    assert summary["brains"] == 14
    assert summary["capabilities"] == len(default_capabilities())
    assert summary["innate_beliefs"] == len(default_innate_beliefs())
    # kalıcı: kimlik/misyon/purpose doğdu
    assert state.get_identity().name == "MIO"
    assert state.get_mission() is not None
    assert state.get_purpose().primary_objective
    # E5 innate inançlarla doğdu
    assert engine.beliefs()  # innate beliefs var
    cog.close()


def test_birth_is_idempotent(state):
    caps = CapabilityRegistry()
    brains = BrainRegistry()
    birth(state, brains, caps)
    v_before = state.get_identity().version
    birth(state, BrainRegistry(), CapabilityRegistry())   # tekrar
    assert state.get_identity().version == v_before        # yeni doğuş yok, kimlik korunur


# ---- Self Awareness Layer (ADR-0002 Madde 3) ----
def test_self_model_answers_the_questions(state):
    caps = CapabilityRegistry()
    brains = BrainRegistry()
    cog = SQLiteBeliefStore(":memory:")
    birth(state, brains, caps, cognitive=CognitiveEngine(cog))
    caps.set_connected("filesystem", True)
    caps.set_connected("web_browser", True)

    aware = SelfAwareness(state, brains, caps,
                          available_models=["local:qwen"], hardware={"ram_gb": 16})
    model = aware.self_model()

    assert model["who_am_i"]["name"] == "MIO"
    assert model["purpose"]["primary_objective"]
    assert len(model["brains"]) == 14
    assert set(model["capabilities"]["connected"]) == {"filesystem", "web_browser"}
    assert "payment" in model["capabilities"]["disconnected"]
    assert model["available_models"] == ["local:qwen"]
    assert model["hardware"]["ram_gb"] == 16
    # kısıtlar Purpose'tan gelir (Financial Rule + ilkeler) + onay gerektiren yetenekler
    cons = " ".join(model["constraints"])
    assert "onay" in cons.lower() and "Para harcamak" in cons
    cog.close()


def test_can_i_honest_answers(state):
    caps = CapabilityRegistry()
    brains = BrainRegistry()
    birth(state, brains, caps)
    aware = SelfAwareness(state, brains, caps)
    ok, reason = aware.can_i("filesystem")
    assert not ok and "bağlı değil" in reason.lower()      # tanımlı ama keşfedilmedi → dürüst hayır
    caps.set_connected("filesystem", True)
    ok, reason = aware.can_i("filesystem")
    assert ok
    ok, reason = aware.can_i("uzay_gemisi")
    assert not ok and "tanımıyorum" in reason.lower()      # kayıtlı değil → dürüst
