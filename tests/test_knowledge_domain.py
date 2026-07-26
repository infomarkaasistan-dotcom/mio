"""MIO Core · Knowledge Domain (Faz 1 · Domain 3) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek innate KnowledgeBase + SQLite write-through repo üzerinden. Validation,
authorization, learn/apply/reinforce/forget, innate koruması (doktriner), deterministik uygulama,
events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.knowledge import (
    ImmutableKnowledgeError,
    KnowEvents,
    KnowledgeDomain,
    KnowledgeRepository,
    KnowledgeType,
    LearnCommand,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus
from mio_core.knowledge import KnowledgeBase, default_innate_knowledge


def _build():
    base = KnowledgeBase()
    base.add_all(default_innate_knowledge())          # MIO doğuştan yetenekli
    repo = KnowledgeRepository(":memory:")
    bus = EventBus(record=True)
    dom = KnowledgeDomain(base, repo, bus=bus)
    return dom, base, repo, bus


@pytest.fixture
def kd():
    return _build()


# ---- UNIT: validation ----
def test_learn_validation(kd):
    d, _b, _r, _bus = kd
    with pytest.raises(ValidationError):
        d.learn("owner", ktype="rule", name="  ", statement="x", when=["a"], then="b")   # boş ad
    with pytest.raises(ValidationError):
        d.learn("owner", ktype="uydurma", name="X", statement="x")                       # geçersiz tip
    with pytest.raises(ValidationError):
        d.learn("owner", ktype="rule", name="X", statement="x")                          # rule: when/then yok
    with pytest.raises(ValidationError):
        d.learn("owner", ktype="concept", name="X", statement="x", domain="uzay")        # geçersiz alan


def test_confidence_clamped(kd):
    d, _b, _r, _bus = kd
    it = d.learn("owner", ktype="concept", name="aşırı", statement="s", confidence=9.0)
    assert it.confidence == 1.0


# ---- UNIT: authorization ----
def test_authorization_rules(kd):
    d, _b, _r, _bus = kd
    with pytest.raises(UnauthorizedError):
        d.apply("yabanci", {"new_expense"})                          # kayıtsız aktör okuyamaz
    with pytest.raises(UnauthorizedError):
        d.learn("Reasoning", ktype="concept", name="X", statement="s")  # okur ama yazamaz
    assert d.learn("Learning", ktype="concept", name="Y", statement="s").id  # yazar aktör geçer


# ---- INTEGRATION: learn write-through + event ----
def test_learn_persists_and_emits(kd):
    d, base, repo, bus = kd
    it = d.learn("Knowledge", ktype="decision_heuristic", name="test-al-ölç",
                 statement="Önce küçük test.", domain="product", when=["belirsiz_talep"],
                 then="Küçük ölçekli test uygula.", confidence=0.8)
    assert base.get(it.id) is not None                               # canlı base'e eklendi
    assert repo.get(it.id) is not None                               # write-through kalıcı
    assert it.source == "learned:Knowledge"                          # köken işaretlendi
    assert any(e["type"] == KnowEvents.LEARNED for e in bus.history())


# ---- INTEGRATION: deterministik uygulama (LLM'siz karar) ----
def test_apply_produces_deterministic_recommendation(kd):
    d, _b, _r, bus = kd
    # innate finansal-onay-kuralı: when=[financial_commitment, no_user_approval]
    recs = d.apply("Executive", {"financial_commitment", "no_user_approval"})
    assert recs and any("Reddet" in r["recommendation"] for r in recs)
    assert d.apply("Executive", {"financial_commitment", "no_user_approval"}) == recs  # determinizm
    assert any(e["type"] == KnowEvents.APPLIED for e in bus.history())


def test_learned_rule_then_applies(kd):
    d, _b, _r, _bus = kd
    d.learn("owner", LearnCommand(ktype="rule", name="yedekle-önce", statement="Riskli işlemden önce yedek.",
            domain="security", when=["riskli_islem"], then="Önce yedek al.", confidence=0.9))
    recs = d.apply("owner", {"riskli_islem"})
    assert any(r["recommendation"] == "Önce yedek al." for r in recs)


# ---- INTEGRATION: reinforce + innate koruması ----
def test_reinforce_living_and_innate_immutable(kd):
    d, base, repo, _bus = kd
    it = d.learn("owner", ktype="concept", name="artan-güven", statement="s", confidence=0.5)
    new_conf = d.reinforce("owner", it.id, delta=0.2)
    assert new_conf == 0.7 and repo.get(it.id).confidence == 0.7     # write-through güncellendi
    innate_id = base.list()[0].id                                    # bir innate öğe
    with pytest.raises(ImmutableKnowledgeError):
        d.reinforce("owner", innate_id, delta=0.1)                   # doktriner: değiştirilemez
    with pytest.raises(NotFoundError):
        d.reinforce("owner", "yok-id")


# ---- INTEGRATION: forget yaşayan bilgi; innate korunur ----
def test_forget_living_only(kd):
    d, base, repo, bus = kd
    it = d.learn("owner", ktype="concept", name="geçici", statement="s")
    d.forget("owner", it.id)
    assert base.get(it.id) is None and repo.get(it.id) is None
    assert any(e["type"] == KnowEvents.FORGOTTEN for e in bus.history())
    innate_id = base.list()[0].id
    with pytest.raises(ImmutableKnowledgeError):
        d.forget("owner", innate_id)                                 # innate silinemez


# ---- INTEGRATION: retrieve + stats + contract ----
def test_retrieve_stats_contract(kd):
    d, _b, _r, _bus = kd
    hits = d.what_do_i_know("Reasoning", "nakit akışı")
    assert any("nakit" in h["statement"].lower() for h in hits)
    s = d.stats()
    assert s["innate"] >= 10 and s["total"] == s["innate"] + s["learned"]
    assert s["applicable"] >= 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "knowledge" and c["version"] == "1.0.0" and "apply" in c["operations"]


# ---- SMOKE: boot() → domain uçtan uca + kalıcılık ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    ws = str(tmp_path / "mio")
    mio = boot(workspace=ws, connect_ollama=False, discover_hw=False)
    # doğuştan innate bilgiyi uygular (LLM yok)
    recs = mio.knowledge_domain.apply("owner", {"new_expense"})
    assert any("ücretsiz" in r["recommendation"].lower() for r in recs)
    learned = mio.knowledge_domain.learn("owner", ktype="rule", name="smoke-kural",
              statement="Test kuralı.", domain="business", when=["smoke_ctx"], then="Uygula.")
    assert mio.knowledge_domain.stats()["learned"] >= 1
    mio.close()
    # yeniden boot → write-through kalıcılık: öğrenilen bilgi geri yüklenir
    mio2 = boot(workspace=ws, connect_ollama=False, discover_hw=False)
    assert mio2.knowledge.get(learned.id) is not None
    assert any(r["recommendation"] == "Uygula." for r in mio2.knowledge_domain.apply("owner", {"smoke_ctx"}))
    mio2.close()
