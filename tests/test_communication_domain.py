"""MIO Core · Communication Domain (Faz 2 · Domain 8) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite konuşma deposu + deterministik niyet sınıflandırma üzerinden.
Validation, authorization, sınıflandırma determinizmi, handler→advisor→fallback öncelik zinciri, çok-turlu
kalıcılık, events ve uçtan-uca akış (LLM'siz çalışabilirlik) doğrulanır."""

import pytest

from mio_core.domains.communication import (
    CommEvents,
    CommunicationDomain,
    ConversationRepository,
    Intent,
    NotFoundError,
    ResponseSource,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(advisor=None):
    bus = EventBus(record=True)
    dom = CommunicationDomain(ConversationRepository(":memory:"), advisor=advisor, bus=bus)
    return dom, bus


@pytest.fixture
def cd():
    return _build()


# ---- UNIT: deterministik sınıflandırma ----
def test_classify_is_deterministic(cd):
    d, _b = cd
    assert d.classify("Merhaba MIO") == Intent.GREETING
    assert d.classify("Sen kimsin?") == Intent.STATUS
    assert d.classify("Sürdürülebilir gelir nedir?") == Intent.QUERY_KNOWLEDGE
    assert d.classify("Bir hedef tanımlamak istiyorum") == Intent.GOAL
    assert d.classify("Bana adım adım bir plan ver") == Intent.PLAN
    assert d.classify("Bu kararı değerlendir") == Intent.REASON
    assert d.classify("xyzzy foobar") == Intent.UNKNOWN
    assert d.classify("Sen kimsin?") == d.classify("Sen kimsin?")   # determinizm


# ---- UNIT: validation + authorization ----
def test_validation_and_authz(cd):
    d, _b = cd
    with pytest.raises(ValidationError):
        d.converse("owner", "   ")
    with pytest.raises(UnauthorizedError):
        d.converse("yabanci", "merhaba")
    with pytest.raises(NotFoundError):
        d.converse("owner", "merhaba", conversation_id="yok-konusma")


# ---- INTEGRATION: LLM'siz çalışır (handler yoksa dürüst fallback) ----
def test_works_without_llm_fallback(cd):
    d, bus = cd                                                     # advisor=None, handler=yok
    out = d.converse("owner", "Bu kararı değerlendir")             # REASON, handler yok
    assert out["intent"] == Intent.REASON and out["source"] == ResponseSource.FALLBACK
    assert out["reply"]                                            # dürüst, boş değil
    greet = d.converse("owner", "merhaba")
    assert greet["intent"] == Intent.GREETING and "MIO" in greet["reply"]
    assert any(e["type"] == CommEvents.REPLIED for e in bus.history())


# ---- INTEGRATION: handler önceliği (advisor'dan önce) ----
def test_handler_takes_priority_over_advisor():
    calls = {"advisor": 0}

    def advisor(prompt):
        calls["advisor"] += 1
        return "LLM cevabı"

    d, _b = _build(advisor=advisor)
    d.register_handler(Intent.STATUS, lambda text, ctx: "Ben MIO, deterministik cevap.")
    out = d.converse("owner", "sen kimsin")
    assert out["source"] == ResponseSource.HANDLER and "deterministik" in out["reply"]
    assert calls["advisor"] == 0                                   # handler cevapladı → LLM çağrılmadı


# ---- INTEGRATION: advisor fallback (handler yok/boş → LLM) ----
def test_advisor_used_when_no_handler():
    d, _b = _build(advisor=lambda prompt: "danışman yanıtı")
    out = d.converse("owner", "rastgele bir soru xyzzy")          # UNKNOWN, handler yok → advisor
    assert out["source"] == ResponseSource.ADVISOR and out["reply"] == "danışman yanıtı"


def test_advisor_failure_degrades_to_fallback():
    def broken(prompt):
        raise RuntimeError("LLM erişilemez")

    d, _b = _build(advisor=broken)
    out = d.converse("owner", "rastgele soru xyzzy")
    assert out["source"] == ResponseSource.FALLBACK                # LLM patladı → dürüst geri-dönüş
    assert out["reply"]


# ---- INTEGRATION: çok-turlu kalıcılık ----
def test_multiturn_persistence(cd):
    d, _b = cd
    first = d.converse("owner", "merhaba")
    cid = first["conversation_id"]
    d.converse("owner", "sen kimsin", conversation_id=cid)
    hist = d.history("owner", cid)
    assert len(hist) == 4 and hist[0]["role"] == "user" and hist[1]["role"] == "assistant"
    assert any(c["id"] == cid for c in d.conversations("owner"))


def test_register_handler_validation(cd):
    d, _b = cd
    with pytest.raises(ValidationError):
        d.register_handler("uydurma-niyet", lambda t, c: "x")


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(cd):
    d, _b = cd
    d.converse("owner", "merhaba")
    s = d.stats()
    assert s["conversations"] >= 1 and s["turns"] >= 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "communication" and "converse" in c["operations"]


# ---- SMOKE: boot() → gerçek handler'lar (LLM'siz deterministik cevaplar) ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    # STATUS handler → öz-modelden gerçek cevap (LLM yok)
    st = mio.communication.converse("owner", "sen kimsin ve ne yapabilirsin")
    assert st["intent"] == Intent.STATUS and st["source"] == ResponseSource.HANDLER
    assert "MIO" in st["reply"]
    # QUERY_KNOWLEDGE handler → innate bilgiden gerçek cevap
    kq = mio.communication.converse("owner", "nakit akışı nedir")
    assert kq["intent"] == Intent.QUERY_KNOWLEDGE and kq["source"] == ResponseSource.HANDLER
    assert "nakit" in kq["reply"].lower()
    # GOAL handler → hedef yok mesajı (deterministik)
    gq = mio.communication.converse("owner", "hedeflerim neler")
    assert gq["intent"] == Intent.GOAL and gq["source"] == ResponseSource.HANDLER
    assert mio.communication.contract()["version"] == "1.0.0"
    mio.close()
