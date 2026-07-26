"""MIO Core · Conversation Domain — üretim testleri: etkileşim mantığı + KATMAN AYRIMI + Executive köprüsü.

Domain platformu bilmez; ConnectorManager çağırmaz; doğrudan cevap göndermez — yalnız CapabilityIntent üretir.
Moderasyon TESPİT eder, KARAR VERMEZ (Executive'e öneri). Deterministik sınıflandırma/spam/flood/hakaret/öncelik,
Madde 24, fake connector ile executed yolu."""

import pytest

from mio_core.domains.conversation import (
    ConversationConfig,
    ConversationDomain,
    ConversationEvents,
    ConversationRepository,
    ModerationFlag,
    Priority,
    UnauthorizedError,
    ValidationError,
    classify_intent,
    moderate_text,
)
from mio_core.events import EventBus


def _build(config=None):
    repo = ConversationRepository(":memory:")
    bus = EventBus(record=True)
    return ConversationDomain(repo, bus=bus, config=config), repo, bus


@pytest.fixture
def cd():
    return _build()


# ---- UNIT: deterministik sınıflandırma + moderasyon ----
def test_classify_intent():
    assert classify_intent("MIO nedir?") == "question"
    assert classify_intent("/start") == "command"
    assert classify_intent("merhaba") == "greeting"
    assert classify_intent("harika iş") == "feedback"
    assert classify_intent("bir cümle") == "statement"


def test_moderate_text_detects():
    assert ModerationFlag.CLEAN in moderate_text("normal mesaj").flags
    assert ModerationFlag.ABUSE in moderate_text("sen aptalsın").flags
    assert ModerationFlag.AD in moderate_text("bedava para www.x.com").flags
    spam = moderate_text("tekrar", repeats=2)
    assert ModerationFlag.SPAM in spam.flags and spam.requires_approval is True   # karar DEĞİL, öneri+onay


def test_authz(cd):
    d, _r, _b = cd
    with pytest.raises(UnauthorizedError):
        d.receive("Reasoning", "u", "x")
    with pytest.raises(ValidationError):
        d.receive("owner", "", "x")


# ---- receive: sınıflandırma + öncelik + moderasyon (cevap YOK) ----
def test_receive_classifies_and_moderates(cd):
    d, _r, bus = cd
    r = d.receive("owner", "alice", "Nasıl çalışıyor?")
    assert r["message"]["intent"] == "question" and r["message"]["priority"] == Priority.HIGH
    assert r["moderation"]["recommendation"] == "allow"
    assert any(e["type"] == ConversationEvents.MESSAGE_RECEIVED for e in bus.history())
    # spam → öneri delete + onay (Executive'e; domain karar vermez). repeats>=2 (3. tekrar) → SPAM.
    for _ in range(3):
        rs = d.receive("owner", "bob", "REKLAM www.spam.com")
    assert ModerationFlag.SPAM in rs["moderation"]["flags"]
    assert rs["moderation"]["requires_approval"] is True
    assert any(e["type"] == ConversationEvents.SPAM_DETECTED for e in bus.history())


# ---- VIP önceliği + queue sıralama ----
def test_vip_priority_and_queue(cd):
    d, _r, _b = cd
    d.set_vip("owner", "vipuser", True)
    d.receive("owner", "normaluser", "bir açıklama")     # normal
    d.receive("owner", "asker", "bu ne?")                # question → high
    d.receive("owner", "vipuser", "selam")               # vip
    q = d.queue("owner")
    assert q[0]["priority"] == Priority.VIP and q[1]["priority"] == Priority.HIGH   # öncelik sırası


# ---- KATMAN AYRIMI: domain connector import ETMEZ (AST) ----
def test_domain_does_not_import_connectors():
    import ast
    from pathlib import Path
    pkg = Path(__file__).resolve().parent.parent / "mio_core" / "domains" / "conversation"
    for py in pkg.glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mod = (node.module if isinstance(node, ast.ImportFrom) else None) or ""
            assert "mio_core.connectors" not in mod, f"{py.name} connector import ediyor (katman ihlali)"


# ---- NİYET üretimi (yürütme YOK) + Madde 24 ----
def test_plan_reply_and_moderation_intent(cd):
    d, _r, bus = cd
    m = d.receive("owner", "u", "soru?")["message"]
    reply = d.plan_reply("owner", m["id"], "cevabım")
    assert reply["capability"] == "conversation.reply" and reply["requires_approval"] is False
    priv = d.plan_reply("owner", m["id"], "özel", private=True)
    assert priv["capability"] == "conversation.private_reply"
    # moderasyon niyeti: ban yüksek-risk → onay
    ban = d.moderation_intent("owner", m["id"], "ban")
    assert ban["capability"] == "conversation.ban" and ban["requires_approval"] is True
    assert any(e["type"] == ConversationEvents.APPROVAL_REQUIRED for e in bus.history())
    with pytest.raises(ValidationError):
        d.moderation_intent("owner", m["id"], "uydurma")


# ---- summary + stats + contract ----
def test_summary_stats_contract(cd):
    d, _r, _b = cd
    d.receive("owner", "a", "soru?")
    d.receive("owner", "b", "açıklama")
    s = d.summarize("owner")
    assert s["messages"] == 2 and s["users"] == 2 and s["pending"] == 2
    st = d.stats()
    assert st["received"] == 2 and st["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "conversation" and "plan_reply" in c["operations"]


# ---- EXECUTIVE KÖPRÜSÜ: appservice niyeti ConnectorManager ile yürütür (domain yürütmez) ----
def test_executive_bridge_reply_and_moderate(tmp_path):
    from mio_core.runtime import boot
    from mio_core import appservice
    from mio_core.connectors import CallableConnector, ConnectorCategory, Cap
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        r = appservice.conversation_receive(mio, "alice", "soru?")
        mid = r["message"]["id"]
        # 1) connector yok → reply unavailable (domain göndermedi; Executive denedi)
        d0 = appservice.conversation_reply(mio, mid, "cevap")
        assert d0["outcome"]["status"] == "connector_unavailable"
        # 2) Communication connector bağla → reply executed + mesaj answered
        sent = []
        mio.connectors.register(CallableConnector(
            "discord", ConnectorCategory.COMMUNICATION,
            handlers={Cap.CONV_REPLY: lambda req: sent.append(req) or {"sent": True},
                      Cap.CONV_DELETE: lambda req: {"deleted": True}}))
        d1 = appservice.conversation_reply(mio, mid, "MIO bir Cognitive OS.")
        assert d1["outcome"]["status"] == "executed" and sent[0]["text"].startswith("MIO")
        assert appservice.conversation_receive.__module__  # appservice yüzeyi mevcut
        # 3) moderation delete yüksek-risk: onaysız requires_approval, onaylı executed
        r2 = appservice.conversation_receive(mio, "bob", "spam")["message"]
        unappr = appservice.conversation_moderate(mio, r2["id"], "delete")
        assert unappr["outcome"]["status"] == "requires_approval"
        appr = appservice.conversation_moderate(mio, r2["id"], "delete", approve=True)
        assert appr["outcome"]["status"] == "executed"
    finally:
        mio.close()
