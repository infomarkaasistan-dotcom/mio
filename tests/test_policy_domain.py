"""MIO Core · Policy Domain (Faz 4 · Domain 14) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite politika deposu + innate anayasal politikalar üzerinden. Deterministik
PDP çözümü (precedence), innate koruması, define/remove/toggle, authorization (admin ayrımı), events ve
uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.policy import (
    ImmutablePolicyError,
    PolicyDomain,
    PolicyEffect,
    PolicyEvents,
    PolicyRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build():
    repo = PolicyRepository(":memory:")
    bus = EventBus(record=True)
    dom = PolicyDomain(repo, bus=bus)          # doğuşta innate politikalar
    return dom, repo, bus


@pytest.fixture
def pol():
    return _build()


# ---- UNIT: doğuştan innate politikalar ----
def test_born_with_innate_policies(pol):
    d, _r, _b = pol
    s = d.stats()
    assert s["innate"] == 3 and s["total"] == 3


# ---- INTEGRATION: anayasal değerlendirme (Financial Rule) ----
def test_financial_commitment_requires_approval(pol):
    d, _r, bus = pol
    r = d.evaluate("Finance", "spend", context_tags=["financial_commitment"])
    assert r["verdict"] == PolicyEffect.REQUIRE_APPROVAL and r["allow"] is False
    ok = d.evaluate("Finance", "spend", context_tags=["financial_commitment"], user_approved=True)
    assert ok["verdict"] == PolicyEffect.REQUIRE_APPROVAL and ok["allow"] is True   # onayla geçer
    assert any(e["type"] == PolicyEvents.GATED for e in bus.history())


def test_no_match_defaults_allow(pol):
    d, _r, _b = pol
    r = d.evaluate("owner", "read_docs", context_tags=["harmless"])
    assert r["verdict"] == PolicyEffect.ALLOW and r["allow"] is True and r["default_used"] is True


# ---- INTEGRATION: deterministik precedence (DENY > REQUIRE_APPROVAL) ----
def test_precedence_deny_wins(pol):
    d, _r, _b = pol
    d.define_policy("owner", "block-danger", PolicyEffect.DENY, conditions=["danger"], priority=10)
    # danger + financial_commitment birlikte → DENY (require_approval'dan üstün), priority düşük olsa da
    r = d.evaluate("owner", "x", context_tags=["danger", "financial_commitment"])
    assert r["verdict"] == PolicyEffect.DENY and r["allow"] is False
    assert r["matched"][0]["effect"] == PolicyEffect.DENY        # sıralamada önce
    approved = d.evaluate("owner", "x", context_tags=["danger"], user_approved=True)
    assert approved["allow"] is False                           # deny onayla bile geçmez


# ---- UNIT: define validation + authorization (admin ayrımı) ----
def test_define_validation_and_admin(pol):
    d, _r, _b = pol
    with pytest.raises(ValidationError):
        d.define_policy("owner", "  ", PolicyEffect.ALLOW)
    with pytest.raises(ValidationError):
        d.define_policy("owner", "p", "uydurma-efekt")
    d.define_policy("owner", "dup", PolicyEffect.ALLOW)
    with pytest.raises(ValidationError):
        d.define_policy("owner", "dup", PolicyEffect.ALLOW)      # tekrar ad
    with pytest.raises(UnauthorizedError):
        d.define_policy("Finance", "p2", PolicyEffect.ALLOW)     # Finance reader ama admin değil
    with pytest.raises(UnauthorizedError):
        d.evaluate("yabanci", "x")                              # kayıtsız aktör


# ---- INTEGRATION: innate koruması ----
def test_innate_immutable(pol):
    d, _r, _b = pol
    innate = next(p for p in d.list_policies("owner") if p["source"] == "innate")
    with pytest.raises(ImmutablePolicyError):
        d.remove_policy("owner", innate["id"])
    with pytest.raises(ImmutablePolicyError):
        d.set_enabled("owner", innate["id"], False)             # devre dışı bırakılamaz
    with pytest.raises(NotFoundError):
        d.remove_policy("owner", "yok-id")


# ---- INTEGRATION: custom politika yaşam-döngüsü ----
def test_custom_policy_lifecycle(pol):
    d, _r, bus = pol
    p = d.define_policy("Security", "deny-export", PolicyEffect.DENY, conditions=["export_pii"], scope="export")
    assert d.evaluate("owner", "export", context_tags=["export_pii"])["verdict"] == PolicyEffect.DENY
    d.set_enabled("owner", p["id"], False)                      # kapat → artık eşleşmez
    assert d.evaluate("owner", "export", context_tags=["export_pii"])["verdict"] == PolicyEffect.ALLOW
    d.remove_policy("owner", p["id"])
    assert any(e["type"] == PolicyEvents.REMOVED for e in bus.history())


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(pol):
    d, _r, _b = pol
    d.evaluate("owner", "x", context_tags=["financial_commitment"])
    s = d.stats()
    assert s["evaluations"] >= 1 and s["gated"] >= 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "policy" and "evaluate" in c["operations"]


# ---- SMOKE: boot() → anayasal PDP uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    assert mio.policy.stats()["innate"] == 3
    r = mio.policy.evaluate("owner", "purchase", context_tags=["irreversible_action"])
    assert r["verdict"] == PolicyEffect.REQUIRE_APPROVAL
    assert mio.policy.evaluate("owner", "purchase", context_tags=["irreversible_action"],
                               user_approved=True)["allow"] is True
    assert mio.policy.contract()["version"] == "1.0.0"
    mio.close()
