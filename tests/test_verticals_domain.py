"""MIO Core · Vertical Domain Brains (Faz 3 · Domain 11) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek KnowledgeDomain (innate) + ReasoningDomain + SQLite advice deposu üzerinden.
8 beyin, deterministik alan tavsiyesi, alan-spesifik guardrail'ler (Financial Rule / geri-alınamaz koruma),
'karar vermez' invariantı, authorization, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.knowledge import KnowledgeDomain, KnowledgeRepository
from mio_core.domains.reasoning import ReasoningDomain, ReasoningRepository
from mio_core.domains.verticals import (
    AdviceRepository,
    GateVerdict,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    VerticalBrains,
    VerticalEvents,
)
from mio_core.events import EventBus
from mio_core.knowledge import KnowledgeBase, default_innate_knowledge


def _build():
    base = KnowledgeBase()
    base.add_all(default_innate_knowledge())
    knowledge = KnowledgeDomain(base, KnowledgeRepository(":memory:"))
    reasoning = ReasoningDomain(knowledge, ReasoningRepository(":memory:"))
    bus = EventBus(record=True)
    v = VerticalBrains(knowledge, AdviceRepository(":memory:"), reasoning=reasoning, bus=bus)
    return v, bus


@pytest.fixture
def vb():
    return _build()


# ---- UNIT: registry ----
def test_registry_has_eight_brains(vb):
    v, _b = vb
    assert v.names() == ["business", "engineering", "finance", "marketing", "operations",
                         "product", "sales", "security"]
    assert v.get("finance").name == "finance"
    assert v["security"].name == "security"                # __getitem__
    assert v.finance.spec.title == "Finance Brain"         # __getattr__
    with pytest.raises(NotFoundError):
        v.get("uydurma")


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(vb):
    v, _b = vb
    with pytest.raises(ValidationError):
        v.finance.advise("owner", "   ")
    with pytest.raises(UnauthorizedError):
        v.finance.advise("yabanci", "bütçe önerisi")


# ---- INTEGRATION: alan-spesifik deterministik tavsiye (karar VERMEZ) ----
def test_finance_advise_uses_domain_rule(vb):
    v, bus = vb
    out = v.finance.advise("owner", "yeni bir araç satın alalım mı")   # focus_tag: new_expense
    assert "ücretsiz" in out["recommendation"].lower()                 # innate 'önce-ücretsiz'
    assert out["confidence"] > 0 and out["decision_authority"] == "Executive"   # KARAR VERMEZ
    assert any(c["source"] == "reasoning" for c in out["considerations"])       # reasoning izi
    assert any(e["type"] == VerticalEvents.ADVISED for e in bus.history())


def test_sales_advise_value_first(vb):
    v, _b = vb
    out = v.sales.advise("owner", "soğuk müşteriye nasıl yaklaşayım")  # focus_tag: cold_lead
    assert "değer-önce" in out["recommendation"].lower()


def test_business_advise_falls_back_to_knowledge(vb):
    v, _b = vb
    out = v.business.advise("owner", "sürdürülebilir gelir nasıl olur")  # focus_tag yok → bilgi referansı
    assert out["recommendation"] and out["confidence"] >= 0.0


# ---- INTEGRATION: guardrail'ler (Anayasa deterministik) ----
def test_finance_financial_rule_guardrail(vb):
    v, bus = vb
    gated = v.finance.assess_action("owner", context_tags=["financial_commitment"])
    assert gated["verdict"] == GateVerdict.NEEDS_APPROVAL and gated["allow"] is False
    assert gated["decision_authority"] == "Executive"
    approved = v.finance.assess_action("owner", context_tags=["financial_commitment"], user_approved=True)
    assert approved["verdict"] == GateVerdict.ALLOW and approved["allow"] is True   # onayla geçer
    assert any(e["type"] == VerticalEvents.GUARDRAIL_GATED for e in bus.history())


def test_security_irreversible_guardrail(vb):
    v, _b = vb
    g = v.security.assess_action("owner", context_tags=["irreversible_action"])
    assert g["verdict"] == GateVerdict.NEEDS_APPROVAL and g["allow"] is False


def test_no_gate_domain_allows(vb):
    v, _b = vb
    g = v.marketing.assess_action("owner", context_tags=["financial_commitment"])  # marketing guardrail'siz
    assert g["allow"] is True and g["verdict"] == GateVerdict.ALLOW


# ---- INTEGRATION: history + explain + stats + contract ----
def test_history_explain_stats_contract(vb):
    v, _b = vb
    a = v.finance.advise("owner", "maliyet analizi")
    assert any(x["id"] == a["id"] for x in v.finance.history("owner"))
    assert v.finance.explain("owner", a["id"])["brain"] == "finance"
    with pytest.raises(NotFoundError):
        v.marketing.explain("owner", a["id"])              # başka beynin tavsiyesi → bulunamaz
    c = v.finance.contract()
    assert c["domain"] == "vertical.finance" and c["version"] == "1.0.0" and "advise" in c["operations"]
    layer = v.stats()
    assert layer["count"] == 8 and layer["advice_total"] >= 1


# ---- SMOKE: boot() → 8 beyin bağlı, uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    assert len(mio.verticals.names()) == 8
    adv = mio.verticals.finance.advise("owner", "reklam bütçesi ayıralım mı")
    assert adv["decision_authority"] == "Executive" and "ücretsiz" in adv["recommendation"].lower()
    gate = mio.verticals.finance.assess_action("owner", context_tags=["financial_commitment"])
    assert gate["verdict"] == GateVerdict.NEEDS_APPROVAL
    assert mio.verticals.engineering.assess_action(
        "owner", context_tags=["irreversible_action"])["verdict"] == GateVerdict.NEEDS_APPROVAL
    assert mio.verticals.contract()["count"] == 8
    mio.close()
