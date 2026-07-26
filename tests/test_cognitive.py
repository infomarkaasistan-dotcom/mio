"""MIO Core · E5 Cognitive Engine — üretim testleri (deterministik, LLM-siz).

Born Capable (ADR-0001) tohumlama, çelişki/çürütme ve E5→E3→E4→E1 uçtan uca entegrasyon.
"""

import pytest

from mio_core.executive import (
    BeliefStore,
    CognitiveEngine,
    ExecutiveReview,
    ExecutiveState,
    GovernanceEngine,
    SQLiteBeliefStore,
    SQLiteExecutiveStateStore,
)


@pytest.fixture
def store(tmp_path):
    s = SQLiteBeliefStore(str(tmp_path / "cog.db"))
    yield s
    s.close()


@pytest.fixture
def engine(store):
    return CognitiveEngine(store)


_SEEDS = [
    {"subject": "reklam", "statement": "Reklam, doğru hedeflenirse büyümeyi hızlandırır.",
     "domain": "business", "valence": 0.7},
    {"subject": "nakit_akisi", "statement": "Pozitif nakit akışı işletmenin hayatta kalması için kritiktir.",
     "domain": "finance", "valence": 0.9},
    {"subject": "mimari", "statement": "LLM asla beyin değildir; deterministik çekirdek esastır.",
     "domain": "strategy", "valence": 0.8},
]


# ---- Born Capable ----
def test_born_with_seeds_once(engine, store):
    n = engine.born_with(_SEEDS)
    assert n == 3
    assert store.count(source="innate") == 3
    # ikinci doğuş yok — innate zaten var
    assert engine.born_with(_SEEDS) == 0
    assert store.count(source="innate") == 3


def test_born_beliefs_are_innate_not_experience(engine):
    engine.born_with(_SEEDS)
    b = engine.beliefs(domain="business")[0]
    assert b.source == "innate" and b.subject == "reklam"


# ---- Çelişki: zıt kanıt sessizce ezmez ----
def test_opposing_evidence_flags_not_overwrites(engine):
    engine.born_with(_SEEDS)
    reklam = engine.beliefs(domain="business")[0]
    # aynı konuda ZIT valans → mevcut inanç revizyona işaretlenir, silinmez
    engine.observe("reklam", "Bu pazarda reklam para kaybettiriyor.", domain="business", valence=-0.8)
    flagged = {b.id for b in engine.contradictions()}
    assert reklam.id in flagged
    assert engine.get(reklam.id).statement.startswith("Reklam")   # eski inanç DURUYOR


def test_refute_flags_belief(engine):
    engine.born_with(_SEEDS)
    b = engine.beliefs(domain="finance")[0]
    engine.refute(b.id, "prediction-error: nakit akışı tahminim tuttu ama strateji yanlıştı")
    assert engine.get(b.id).flagged_for_revision
    assert any(x["id"] == b.id for x in engine.flagged_for_revision())


# ---- BeliefSource sözleşmesi ----
def test_mark_revised_clears_flag_and_lowers_confidence(engine):
    engine.born_with(_SEEDS)
    b = engine.beliefs(domain="business")[0]
    engine.refute(b.id, "çürütüldü")
    before = engine.get(b.id).confidence
    engine.mark_revised(b.id, note="güncellendi")
    after = engine.get(b.id)
    assert after.flagged_for_revision is False and after.status == "revised"
    assert after.confidence == pytest.approx(round(before - 0.2, 3))


def test_store_satisfies_protocol(store):
    assert isinstance(store, BeliefStore)


def test_persistence(tmp_path):
    path = str(tmp_path / "c.db")
    s1 = SQLiteBeliefStore(path)
    CognitiveEngine(s1).born_with(_SEEDS)
    s1.close()
    s2 = SQLiteBeliefStore(path)
    assert CognitiveEngine(s2).beliefs()  # innate inançlar kalıcı
    assert s2.count(source="innate") == 3
    s2.close()


# ---- E5 → E3 → E4 → E1 uçtan uca ----
def test_cognitive_feeds_executive_review(tmp_path):
    cog = SQLiteBeliefStore(str(tmp_path / "cog.db"))
    est = SQLiteExecutiveStateStore(str(tmp_path / "exec.db"))
    engine = CognitiveEngine(cog)
    state = ExecutiveState(est)
    state.ensure_identity("MIO")
    gov = GovernanceEngine(state)

    # Born Capable: innate inançlarla doğ
    engine.born_with(_SEEDS)
    reklam = engine.beliefs(domain="business")[0]
    # Yaşayarak: bir tahmin-hatası innate inancı çürüttü
    engine.refute(reklam.id, "prediction-error: reklam ROAS beklenenin çok altında")

    # E3 review — E5 BeliefSource olarak bağlı → Belief Revision E4'ten geçip E1'e yazılır
    review = ExecutiveReview(state, gov, belief_source=engine)
    report = review.run()

    assert len(report.belief_reviews) == 1
    br = report.belief_reviews[0]
    assert br.belief_id == reklam.id and br.action == "revised"
    # E1 defterinde belief_revision kararı var
    assert state.get_decision(br.decision_id).kind == "belief_revision"
    # E5 inancı revize edildi (işaret temizlendi, statü revised)
    assert engine.get(reklam.id).status == "revised"
    assert engine.get(reklam.id).flagged_for_revision is False

    cog.close()
    est.close()
