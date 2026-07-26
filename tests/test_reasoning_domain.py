"""MIO Core · Reasoning Domain (Faz 1 · Domain 4) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek KnowledgeDomain (innate bilgi + muhakeme şablonu) + E5 CognitiveEngine +
SQLite iz deposu üzerinden. Validation, authorization, deterministik deduce/deliberate, tutarlılık denetimi,
açıklanabilirlik (explain), events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.knowledge import KnowledgeDomain, KnowledgeRepository
from mio_core.domains.reasoning import (
    NotFoundError,
    ReasonEvents,
    ReasoningDomain,
    ReasoningKind,
    ReasoningRepository,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus
from mio_core.executive import CognitiveEngine, SQLiteBeliefStore
from mio_core.knowledge import KnowledgeBase, default_innate_knowledge


def _build():
    base = KnowledgeBase()
    base.add_all(default_innate_knowledge())          # innate bilgi + 'karar-muhakemesi' şablonu
    knowledge = KnowledgeDomain(base, KnowledgeRepository(":memory:"))
    cognitive = CognitiveEngine(SQLiteBeliefStore(":memory:"))
    bus = EventBus(record=True)
    dom = ReasoningDomain(knowledge, ReasoningRepository(":memory:"), cognitive=cognitive, bus=bus)
    return dom, knowledge, cognitive, bus


@pytest.fixture
def rd():
    return _build()


# ---- UNIT: validation ----
def test_deduce_requires_context(rd):
    d, _k, _c, _b = rd
    with pytest.raises(ValidationError):
        d.deduce("owner", set())                         # bağlam yok


def test_deliberate_validation(rd):
    d, _k, _c, _b = rd
    with pytest.raises(ValidationError):
        d.deliberate("owner", "  ")                       # boş konu
    with pytest.raises(ValidationError):
        d.deliberate("owner", "konu", template="yok-şablon")  # geçersiz şablon


# ---- UNIT: authorization ----
def test_authorization(rd):
    d, _k, _c, _b = rd
    with pytest.raises(UnauthorizedError):
        d.deduce("yabanci", {"new_expense"})
    with pytest.raises(UnauthorizedError):
        d.consistency_report("yabanci")


# ---- INTEGRATION: deduce deterministik + iz + event ----
def test_deduce_deterministic_and_traces(rd):
    d, _k, _c, bus = rd
    r1 = d.deduce("Executive", {"new_expense"})           # innate 'önce-ücretsiz' heuristik
    assert r1["matches"] >= 1 and "ücretsiz" in r1["conclusion"].lower()
    assert r1["confidence"] > 0 and r1["trace_id"]
    r2 = d.deduce("Executive", {"new_expense"})
    assert r1["conclusion"] == r2["conclusion"] and r1["confidence"] == r2["confidence"]  # determinizm
    assert any(e["type"] == ReasonEvents.DEDUCED for e in bus.history())


# ---- INTEGRATION: deliberate şablonu + kanıt eşleme ----
def test_deliberate_maps_evidence_to_steps(rd):
    d, knowledge, _c, bus = rd
    # 'Risk nedir?' adımına eşlenecek yaşayan kural öğren
    knowledge.learn("owner", ktype="rule", name="risk-değerlendirme", statement="Riski değerlendir.",
                    domain="security", when=["ctx_risk"], then="Risk düşükse ilerle, değilse dur.")
    out = d.deliberate("owner", "yeni pazara giriş", context_tags={"ctx_risk"})
    template = knowledge.list_knowledge("owner", ktype="reasoning_template")[0]
    assert len(out["steps"]) == len(template["steps"])    # şablonun tüm adımları
    risk_step = next(s for s in out["steps"] if "Risk" in s["question"])
    assert any("risk" in ev["text"].lower() for ev in risk_step["evidence"])  # kanıt eşlendi
    assert 0.0 < out["coverage"] <= 1.0
    assert any(e["type"] == ReasonEvents.DELIBERATED for e in bus.history())


def test_deliberate_no_fabrication(rd):
    d, _k, _c, _b = rd
    out = d.deliberate("owner", "tamamen-alakasız-konu-xyz", context_tags=set())
    assert all(s["evidence"] == [] for s in out["steps"])  # kanıt yoksa uydurmaz
    assert out["coverage"] == 0.0


# ---- INTEGRATION: tutarlılık denetimi (E5 çelişki) ----
def test_consistency_report_surfaces_contradiction(rd):
    d, _k, cognitive, bus = rd
    cognitive.observe("proje-x", "iyi gidiyor", valence=0.8)
    cognitive.observe("proje-x", "kötü gidiyor", valence=-0.8)   # zıt valans → çelişki işareti
    rep = d.consistency_report("Executive")
    assert rep["consistent"] is False and rep["conflicts"] >= 1
    assert any("proje-x" in c["subject"] for c in rep["contradictions"])
    assert any(e["type"] == ReasonEvents.CONSISTENCY_CHECKED for e in bus.history())


# ---- INTEGRATION: explain + history + stats + contract ----
def test_explain_history_stats_contract(rd):
    d, _k, _c, _b = rd
    r = d.deduce("owner", {"new_expense"})
    tr = d.explain("owner", r["trace_id"])
    assert tr["kind"] == ReasoningKind.DEDUCE and tr["id"] == r["trace_id"]
    with pytest.raises(NotFoundError):
        d.explain("owner", "yok-iz")
    hist = d.history("owner", kind=ReasoningKind.DEDUCE)
    assert any(t["id"] == r["trace_id"] for t in hist)
    s = d.stats()
    assert s["traces"] >= 1 and s["deduced"] >= 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "reasoning" and c["version"] == "1.0.0" and "deliberate" in c["operations"]


# ---- SMOKE: boot() → domain uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    r = mio.reasoning.deduce("owner", {"financial_commitment", "no_user_approval"})
    assert r["matches"] >= 1 and "reddet" in r["conclusion"].lower()   # innate finansal kural (LLM yok)
    delib = mio.reasoning.deliberate("owner", "gelir hedefi", context_tags={"new_expense"})
    assert len(delib["steps"]) >= 4 and delib["trace_id"]
    assert mio.reasoning.consistency_report("owner")["consistent"] is True  # doğuşta çelişki yok
    assert mio.reasoning.contract()["version"] == "1.0.0"
    mio.close()
