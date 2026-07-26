"""MIO Core · Learning Domain (Faz 1 · Domain 6) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek KnowledgeDomain + E5 CognitiveEngine + SQLite öğrenme deposu üzerinden.
Validation, authorization, güven revizyonu (başarı/başarısızlık), innate koruması, inanç çürütme,
heuristik emergence (deterministik), events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.knowledge import KnowledgeDomain, KnowledgeRepository
from mio_core.domains.learning import (
    LearnEvents,
    LearningDomain,
    LearningRepository,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus
from mio_core.executive import CognitiveEngine, SQLiteBeliefStore
from mio_core.knowledge import KnowledgeBase, default_innate_knowledge


def _build():
    base = KnowledgeBase()
    base.add_all(default_innate_knowledge())
    knowledge = KnowledgeDomain(base, KnowledgeRepository(":memory:"))
    cognitive = CognitiveEngine(SQLiteBeliefStore(":memory:"))
    bus = EventBus(record=True)
    dom = LearningDomain(LearningRepository(":memory:"), knowledge=knowledge, cognitive=cognitive, bus=bus)
    return dom, knowledge, cognitive, bus


@pytest.fixture
def ld():
    return _build()


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(ld):
    d, _k, _c, _b = ld
    with pytest.raises(ValidationError):
        d.record_outcome("owner", "  ", success=True)
    with pytest.raises(UnauthorizedError):
        d.record_outcome("yabanci", "eylem", success=True)
    with pytest.raises(UnauthorizedError):
        d.consolidate("yabanci")


# ---- INTEGRATION: güven revizyonu (başarı → +, başarısızlık → −) ----
def test_outcome_reinforces_and_penalizes_knowledge(ld):
    d, knowledge, _c, bus = ld
    item = knowledge.learn("owner", ktype="concept", name="öğrenilen-kavram", statement="s", confidence=0.5)
    d.record_outcome("Learning", "kavramı kullan", success=True, knowledge_id=item.id)
    assert knowledge.list_knowledge("owner")  # sanity
    after_success = next(k for k in knowledge.list_knowledge("owner") if k["id"] == item.id)["confidence"]
    assert after_success == 0.55                                   # +reinforce_step
    d.record_outcome("Learning", "kavramı kullan", success=False, knowledge_id=item.id)
    after_fail = next(k for k in knowledge.list_knowledge("owner") if k["id"] == item.id)["confidence"]
    assert after_fail == 0.50                                      # −penalize_step
    assert any(e["type"] == LearnEvents.KNOWLEDGE_REINFORCED for e in bus.history())


def test_innate_knowledge_not_updatable(ld):
    d, knowledge, _c, _b = ld
    innate_id = knowledge.list_knowledge("owner")[0]["id"]         # bir innate öğe
    ev = d.record_outcome("Learning", "innate dene", success=True, knowledge_id=innate_id)
    assert any("güncellenemedi" in eff for eff in ev["effects"])   # doktriner: dürüstçe atlandı, patlama yok


# ---- INTEGRATION: inanç çürütme (yalnız başarısızlıkta) ----
def test_failure_refutes_belief(ld):
    d, _k, cognitive, bus = ld
    b = cognitive.observe("pazar", "talep yüksek", confidence=0.7, valence=0.6)
    d.record_outcome("Executive", "kampanya", success=False, belief_id=b.id,
                     expected="yüksek dönüşüm", actual="düşük dönüşüm")
    assert cognitive.get(b.id).flagged_for_revision is True        # E5'te revizyona işaretlendi
    assert any(e["type"] == LearnEvents.BELIEF_REFUTED for e in bus.history())


# ---- INTEGRATION: heuristik emergence (deterministik) ----
def test_emergence_from_repeated_success(ld):
    d, knowledge, _c, bus = ld
    for _ in range(3):                                             # emergence_min_successes = 3
        d.record_outcome("Learning", "erken-test", success=True, tags=["belirsiz_talep"])
    res = d.consolidate("Learning")
    assert res["promoted"] == 1
    # yeni heuristik uygulanabilir: bağlam etiketi geldiğinde öneri üretir (LLM'siz)
    recs = knowledge.apply("Reasoning", {"belirsiz_talep"})
    assert any("erken-test" in r["recommendation"] for r in recs)
    assert any(e["type"] == LearnEvents.HEURISTIC_EMERGED for e in bus.history())
    assert d.consolidate("Learning")["promoted"] == 0             # idempotent (tekrar üretmez)


def test_no_emergence_without_context_tag(ld):
    d, _k, _c, _b = ld
    for _ in range(3):
        d.record_outcome("Learning", "etiketsiz-eylem", success=True)   # bağlam etiketi yok
    assert d.consolidate("Learning")["promoted"] == 0            # uygulanabilir kural kurulamaz → dürüst


# ---- INTEGRATION: lessons + stats + contract ----
def test_lessons_stats_contract(ld):
    d, _k, _c, _b = ld
    d.record_outcome("owner", "deneme", success=True, lesson="Küçük başla, hızlı ölç.")
    d.record_outcome("owner", "deneme2", success=False)
    less = d.lessons("owner")
    assert any(l["lesson"] == "Küçük başla, hızlı ölç." for l in less)
    s = d.stats()
    assert s["total"] == 2 and s["successes"] == 1 and s["failures"] == 1
    assert s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "learning" and "consolidate" in c["operations"]


# ---- SMOKE: boot() → domain uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    for _ in range(3):
        mio.learning.record_outcome("Learning", "otomasyon-kur", success=True, tags=["repetitive_task"])
    assert mio.learning.consolidate("Learning")["promoted"] >= 1
    recs = mio.knowledge_domain.apply("owner", {"repetitive_task"})   # emergent + innate birlikte
    assert any("otomasyon-kur" in r["recommendation"] for r in recs)
    assert mio.learning.stats()["successes"] >= 3
    assert mio.learning.contract()["version"] == "1.0.0"
    mio.close()
