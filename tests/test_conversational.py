"""MIO Core · Conversational Orchestrator — doğal dil (Türkçe) → Intent → mevcut appservice işlemleri.

Orkestrasyon katmanı (yeni mimari YOK): deterministik intent + mevcut appservice'e yönlendirme. Diacritic-duyarsız
(yardım==yardim), kök/önek eşleşme (mesaj→mesajlari), konuşma bağlamı (referans), asla çökmez, CLI/HTTP entegrasyon."""

import pytest

from mio_core.runtime import boot
from mio_core import appservice
from mio_core.cli import run_command, dispatch
from mio_core.http_api import route_request
from mio_core.cli_ui import UI


@pytest.fixture
def mio(tmp_path):
    m = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    yield m
    m.close()


# ---- deterministik intent sınıflandırma (diacritic-duyarsız + kök/önek) ----
@pytest.mark.parametrize("text,expected", [
    ("merhaba", "greeting"), ("Selam", "greeting"),
    ("durum nedir", "status"), ("şirketin durumu ne", "status"),
    ("saglik nasil", "diagnose"), ("sağlık kontrolü", "diagnose"),
    ("donanim durumu", "hardware"), ("GPU nasıl", "hardware"),
    ("modeller neler", "models"),
    ("sunum hazirla", "present"), ("podcast üret", "present"),
    ("mesajlari goster", "conversation"), ("sohbet özeti", "conversation"),
    ("is akislari", "workflow"), ("iş akışları neler", "workflow"),
    ("baglan", "connect"), ("bağlantıları göster", "connect"),
    ("yardim", "help"), ("ne yapabilirsin", "help"),
])
def test_intent_classification(mio, text, expected):
    assert appservice.converse(mio, text)["intent"] == expected


def test_diacritic_insensitive(mio):
    # aynı anlam, diacritic'li ve diacritic'siz → aynı intent
    assert appservice.converse(mio, "yardım")["intent"] == appservice.converse(mio, "yardim")["intent"]
    assert appservice.converse(mio, "iş akışı")["intent"] == appservice.converse(mio, "is akisi")["intent"]


# ---- yönlendirme mevcut appservice'e delege eder (yeni mimari yok) ----
def test_routes_to_existing_services(mio):
    r = appservice.converse(mio, "durum nedir")
    assert r["intent"] == "status" and "System Ready" in r["response"]
    assert r["data"]["executive_score"] == appservice.executive_summary(mio)["executive_score"]
    d = appservice.converse(mio, "sağlık")
    assert d["intent"] == "diagnose" and "Executive Score" in d["response"]


# ---- konuşma bağlamı (referans: 'devam et' önceki niyeti sürdürür) ----
def test_conversational_memory_reference(mio):
    appservice.converse(mio, "iş akışları")           # last_intent = workflow
    ref = appservice.converse(mio, "devam et")        # referans → workflow'u sürdürür
    assert ref["intent"] == "workflow"
    ctx = mio.conversational.context()
    assert ctx["turns"] >= 2 and ctx["last_intent"] == "workflow"


# ---- boş/anlaşılmaz girdi çökmez ----
def test_empty_and_unknown_never_crash(mio):
    assert appservice.converse(mio, "")["intent"] == "empty"
    u = appservice.converse(mio, "asdfghjkl qwerty")  # anlamsız
    assert u["intent"] == "unknown" and u["response"]   # öneri döner, çökmez


# ---- greeting Executive kimliğiyle yanıtlar ----
def test_greeting_is_executive(mio):
    r = appservice.converse(mio, "merhaba")
    assert "MIO Executive" in r["response"] and r["data"]["executive_score"] >= 0


# ---- CLI entegrasyonu: 'ask' komutu + doğal dil yönlendirme ----
def test_cli_ask_command(mio):
    code, out = run_command(mio, ["ask", "durum", "nedir"])
    assert code == 0
    # rich render → CEO yanıtı
    ui = UI(color=False)
    _c, rich = run_command(mio, ["ask", "yardım"], style="rich", ui=ui)
    assert "MIO Executive" in rich


def test_cli_known_command_still_works(mio):
    # geliştirici komutları bozulmadı (backward-compat)
    assert run_command(mio, ["domains"])[0] == 0
    _c, _k, data = dispatch(mio, ["ask", "donanım"])
    assert data["intent"] == "hardware"


# ---- HTTP entegrasyonu: POST /converse (aynı DTO — interface eşitliği) ----
def test_http_converse(mio):
    st, data = route_request(mio, "POST", "/converse", {}, {"text": "iş akışları neler"})
    assert st == 200 and data["intent"] == "workflow"
    # CLI dispatch ile HTTP AYNI DTO
    _c, _k, cli_data = dispatch(mio, ["ask", "iş akışları neler"])
    assert cli_data["intent"] == data["intent"]
