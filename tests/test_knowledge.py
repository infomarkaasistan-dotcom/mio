"""MIO Core · Innate Knowledge (ADR-0002 Madde 5) — üretim testleri (deterministik, LLM-siz).

Tipli bilişsel yapılar + apply() (bilgi KARAR ÜRETİR) + retrieve + birth() tohumlaması. "Bilgi okunmaz,
karar üretmek için kullanılır" ilkesini doğrular.
"""

import pytest

from mio_core.born import birth
from mio_core.brains import BrainRegistry
from mio_core.capability import CapabilityRegistry
from mio_core.executive import ExecutiveState, SQLiteExecutiveStateStore
from mio_core.knowledge import (
    KNOWLEDGE_DOMAINS,
    KnowledgeBase,
    KnowledgeItem,
    KnowledgeType,
    default_innate_knowledge,
)


@pytest.fixture
def kb():
    b = KnowledgeBase()
    b.add_all(default_innate_knowledge())
    return b


# ---- Tipler + apply (bilgi karar üretir) ----
def test_apply_free_first_heuristic(kb):
    recs = kb.apply({"new_expense"})
    assert recs and "ücretsiz" in recs[0].recommendation.lower()
    assert recs[0].ktype == KnowledgeType.DECISION_HEURISTIC.value


def test_apply_financial_rule_needs_both_conditions(kb):
    # tek koşul → uygulanmaz
    assert kb.apply({"financial_commitment"}) == [] or all(
        r.name != "finansal-onay-kuralı" for r in kb.apply({"financial_commitment"}))
    # iki koşul → uygulanır (onay iste/reddet)
    recs = kb.apply({"financial_commitment", "no_user_approval"})
    assert any(r.name == "finansal-onay-kuralı" for r in recs)
    top = next(r for r in recs if r.name == "finansal-onay-kuralı")
    assert "onay" in top.recommendation.lower()


def test_apply_automation_and_empty_context(kb):
    assert any("otomasyon" in r.recommendation.lower() for r in kb.apply({"repetitive_task"}))
    assert kb.apply(set()) == []                       # bağlam yok → uygulama yok


def test_apply_sorted_by_confidence(kb):
    kb.add(KnowledgeItem(KnowledgeType.DECISION_HEURISTIC, "h-low", when=["ctx"], then="düşük", confidence=0.3))
    kb.add(KnowledgeItem(KnowledgeType.RULE, "r-high", when=["ctx"], then="yüksek", confidence=0.95))
    recs = kb.apply({"ctx"})
    assert recs[0].name == "r-high" and recs[-1].name == "h-low"


# ---- Retrieve (referans bilgi) ----
def test_retrieve_finds_relevant(kb):
    hits = kb.retrieve("sürdürülebilir gelir")
    assert hits and any("gelir" in h.name for h in hits)
    assert kb.retrieve("kuantum fiziği") == []         # ilgisiz → uydurmaz


def test_list_by_type_and_domain(kb):
    principles = kb.list(ktype=KnowledgeType.PRINCIPLE)
    assert principles and all(p.ktype == KnowledgeType.PRINCIPLE for p in principles)
    finance = kb.list(domain="finance")
    assert finance and all(i.domain == "finance" for i in finance)


# ---- Alanlar (ADR-0002 Madde 1) ----
def test_knowledge_domains_decomposed():
    assert len(KNOWLEDGE_DOMAINS) == 15                # ayrıştırılmış eğitim alanları
    for d in ("business", "finance", "marketing", "security", "decision_science", "systems_thinking"):
        assert d in KNOWLEDGE_DOMAINS


def test_innate_knowledge_has_active_and_reference_types():
    items = default_innate_knowledge()
    types = {i.ktype for i in items}
    assert KnowledgeType.RULE in types and KnowledgeType.DECISION_HEURISTIC in types
    assert KnowledgeType.CONCEPT in types and KnowledgeType.PRINCIPLE in types
    assert KnowledgeType.MENTAL_MODEL in types and KnowledgeType.REASONING_TEMPLATE in types


# ---- birth() innate bilgiyle doğurur ----
def test_birth_seeds_knowledge():
    state = ExecutiveState(SQLiteExecutiveStateStore(":memory:"))
    kb = KnowledgeBase()
    summary = birth(state, BrainRegistry(), CapabilityRegistry(), knowledge=kb)
    assert summary["innate_knowledge"] == len(default_innate_knowledge())
    assert kb.count() > 0
    # doğuştan bilgi hemen KARAR ÜRETİR
    assert kb.apply({"new_expense"})
    # idempotent — tekrar tohumlanmaz
    birth(state, BrainRegistry(), CapabilityRegistry(), knowledge=kb)
    assert kb.count() == len(default_innate_knowledge())
