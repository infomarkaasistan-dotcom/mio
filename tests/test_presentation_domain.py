"""MIO Core · Presentation Domain — üretim testleri: sunum mantığı + KATMAN AYRIMI + Executive köprüsü.

Domain yalnız CapabilityIntent üretir (ConnectorManager ÇAĞIRMAZ); Executive (appservice) yürütür. Deterministik
senaryo/akış/zaman/slayt, Madde 24 (yayın niyeti onay), dış-sistem-bilmezlik, fake connector ile executed yolu."""

import pytest

from mio_core.domains.presentation import (
    PresentationDomain,
    PresentationEvents,
    PresentationRepository,
    Pace,
    ScriptKind,
    UnauthorizedError,
    ValidationError,
    estimate_seconds,
)
from mio_core.events import EventBus


def _build():
    repo = PresentationRepository(":memory:")
    bus = EventBus(record=True)
    return PresentationDomain(repo, bus=bus), repo, bus


@pytest.fixture
def pd():
    return _build()


# ---- UNIT: deterministik süre + validation + authz ----
def test_estimate_and_validation(pd):
    d, _r, _b = pd
    assert estimate_seconds("bir iki üç dört beş", Pace.NORMAL) > 0
    assert estimate_seconds("", Pace.NORMAL) == 0
    with pytest.raises(UnauthorizedError):
        d.create_script("Reasoning", "x")            # writer değil
    with pytest.raises(ValidationError):
        d.create_script("owner", "x", kind="uydurma")


# ---- create + outline (deterministik senaryo) ----
def test_outline_to_script_deterministic(pd):
    d, _r, bus = pd
    s = d.outline_to_script("owner", "Sunum", ["Giriş konusu", "Ana fikir", "Sonuç"], kind=ScriptKind.WEBINAR)
    assert s["kind"] == "webinar" and len(s["segments"]) == 5   # intro + 3 + outro
    assert s["segments"][0]["kind"] == "intro" and s["segments"][-1]["kind"] == "outro"
    assert len(s["slides"]) == 3
    assert any(e["type"] == PresentationEvents.SCRIPT_CREATED for e in bus.history())


# ---- KATMAN AYRIMI: domain connector modülü import ETMEZ (AST — docstring değil, gerçek import) ----
def test_domain_does_not_import_connectors():
    import ast
    from pathlib import Path
    pkg = Path(__file__).resolve().parent.parent / "mio_core" / "domains" / "presentation"
    for py in pkg.glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mod = (node.module if isinstance(node, ast.ImportFrom) else None) or ""
            names = [a.name for a in node.names] if isinstance(node, (ast.Import, ast.ImportFrom)) else []
            assert "mio_core.connectors" not in mod, f"{py.name} connector import ediyor (katman ihlali)"
            assert not any("connectors" in n for n in names), f"{py.name} connector import ediyor"


# ---- plan_delivery: NİYET üretir (yürütme YOK) + Madde 24 işareti ----
def test_plan_delivery_produces_intents_not_execution(pd):
    d, _r, bus = pd
    s = d.outline_to_script("owner", "Yayın", ["A", "B"], kind=ScriptKind.LIVESTREAM)
    plan = d.plan_delivery("owner", s["id"])
    caps = [i["capability"] for i in plan["intents"]]
    assert "stream.start" in caps and "speech.synthesize" in caps and "stream.stop" in caps
    # canlı yayın niyeti yüksek-risk (onay gerekir)
    start = next(i for i in plan["intents"] if i["capability"] == "stream.start")
    assert start["requires_approval"] is True
    synth = next(i for i in plan["intents"] if i["capability"] == "speech.synthesize")
    assert synth["requires_approval"] is False
    assert any(e["type"] == PresentationEvents.DELIVERY_PLANNED for e in bus.history())


# ---- intent(): soyut hedef → capability ----
def test_abstract_intent_mapping(pd):
    d, _r, _b = pd
    assert d.intent("owner", "konuş" if False else "speak", request={"text": "merhaba"})["capability"] == "speech.synthesize"
    assert d.intent("owner", "golive")["capability"] == "stream.start"
    assert d.intent("owner", "golive")["requires_approval"] is True
    assert d.intent("owner", "subtitle")["capability"] == "subtitle.generate"


# ---- oturum + slayt (deterministik durum makinesi + slayt niyeti) ----
def test_session_and_slide_advance(pd):
    d, _r, bus = pd
    s = d.outline_to_script("owner", "S", ["a", "b", "c"], kind=ScriptKind.SLIDES)
    sess = d.start_session("owner", s["id"])
    adv = d.advance_slide("owner", sess["id"], direction="next")
    assert adv["session"]["slide_cursor"] == 1 and adv["intent"]["capability"] == "slide.next"
    d.advance_slide("owner", sess["id"], direction="previous")
    ended = d.end_session("owner", sess["id"])
    assert ended["status"] == "ended"
    assert any(e["type"] == PresentationEvents.SLIDE_CHANGED for e in bus.history())


# ---- stats + contract ----
def test_stats_contract(pd):
    d, _r, _b = pd
    d.create_script("owner", "X", kind=ScriptKind.PODCAST)
    st = d.stats()
    assert st["scripts"] == 1 and st["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "presentation" and "plan_delivery" in c["operations"]
    assert "avatar" in c["script_kinds"] and "webinar" in c["script_kinds"]


# ---- EXECUTIVE KÖPRÜSÜ: appservice niyetleri ConnectorManager ile yürütür (domain yürütmez) ----
def test_executive_bridge_deliver(tmp_path):
    from mio_core.runtime import boot
    from mio_core import appservice
    from mio_core.connectors import CallableConnector, ConnectorCategory, Cap
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    try:
        s = appservice.presentation_outline(mio, "Podcast", ["bölüm1", "bölüm2"], kind=ScriptKind.PODCAST)
        # 1) connector yok → hepsi connector_unavailable (dürüst, çökmez)
        d0 = appservice.presentation_deliver(mio, s["id"])
        assert d0["executed"] == 0
        assert all(r["outcome"]["status"] == "connector_unavailable" for r in d0["results"])
        # 2) Media TTS connector bağla (Executive/ConnectorManager tarafı) → seslendirmeler executed
        mio.connectors.register(CallableConnector(
            "tts", ConnectorCategory.MEDIA,
            handlers={Cap.SPEECH_SYNTHESIZE: lambda req: {"audio": "wav://x", "len": len(req.get("text", ""))},
                      Cap.PODCAST_RENDER: lambda req: {"file": "podcast.mp3"}}))
        d1 = appservice.presentation_deliver(mio, s["id"])
        assert d1["executed"] >= 2                    # seslendirme niyetleri yürütüldü
        assert any(r["capability"] == "speech.synthesize" and r["outcome"]["status"] == "executed"
                   for r in d1["results"])
    finally:
        mio.close()
