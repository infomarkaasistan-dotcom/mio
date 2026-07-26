"""MIO Core · Perception Domain (Faz 2 · Domain 10) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite percept deposu + gerçek MemoryDomain + E5 CognitiveEngine üzerinden.
Validation, authorization, deterministik normalizasyon/belirginlik, bilişe yönlendirme (E5 belief + Memory
epizodik), dikkat tetiği, kayıpsızlık, events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.memory import MemoryDomain, MemoryRepository, MemoryType
from mio_core.domains.perception import (
    PerceiveEvents,
    PerceptKind,
    PerceptionDomain,
    PerceptionRepository,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus
from mio_core.executive import CognitiveEngine, SQLiteBeliefStore


def _build(memory=True, cognitive=True):
    mem = MemoryDomain(MemoryRepository(":memory:")) if memory else None
    cog = CognitiveEngine(SQLiteBeliefStore(":memory:")) if cognitive else None
    bus = EventBus(record=True)
    dom = PerceptionDomain(PerceptionRepository(":memory:"), memory=mem, cognitive=cog, bus=bus)
    return dom, mem, cog, bus


@pytest.fixture
def pcd():
    return _build()


# ---- UNIT: validation ----
def test_perceive_validation(pcd):
    d, _m, _c, _b = pcd
    with pytest.raises(ValidationError):
        d.perceive("owner", "  ", "içerik")               # boş kaynak
    with pytest.raises(ValidationError):
        d.perceive("owner", "sensor", "  ")               # boş içerik
    with pytest.raises(ValidationError):
        d.perceive("owner", "sensor", "x", kind="uydurma")


# ---- UNIT: authorization ----
def test_authorization(pcd):
    d, _m, _c, _b = pcd
    with pytest.raises(UnauthorizedError):
        d.perceive("yabanci", "sensor", "x")
    with pytest.raises(UnauthorizedError):
        d.attention("yabanci")


# ---- UNIT: deterministik belirginlik ----
def test_default_salience_by_kind(pcd):
    d, _m, _c, _b = pcd
    assert d.perceive("owner", "s", "x", kind=PerceptKind.ALERT)["salience"] == 0.9
    assert d.perceive("owner", "s", "x", kind=PerceptKind.SIGNAL)["salience"] == 0.3
    assert d.perceive("owner", "s", "x", kind=PerceptKind.METRIC, salience=0.55)["salience"] == 0.55


# ---- INTEGRATION: gözlem → E5 inanç oluşumu ----
def test_observation_routes_to_cognitive(pcd):
    d, _m, cognitive, bus = pcd
    p = d.perceive("owner", "pazar-verisi", "talep artıyor", kind=PerceptKind.OBSERVATION,
                   subject="talep", valence=0.6)
    assert "cognitive" in p["routed"]
    beliefs = cognitive.beliefs()
    assert any(b.subject == "talep" and "talep artıyor" in b.statement for b in beliefs)
    assert any(e["type"] == PerceiveEvents.ROUTED for e in bus.history())


# ---- INTEGRATION: her percept → epizodik bellek ----
def test_percept_routes_to_memory(pcd):
    d, memory, _c, _b = pcd
    p = d.perceive("owner", "log", "disk %90 doldu", kind=PerceptKind.ALERT, tags=["altyapı"])
    assert "memory" in p["routed"]
    hits = memory.recall("owner", "disk doldu", mtype=MemoryType.EPISODIC)
    assert any("disk" in h["content"] for h in hits)


# ---- INTEGRATION: dikkat tetiği ----
def test_attention_trigger_and_query(pcd):
    d, _m, _c, bus = pcd
    d.perceive("owner", "monitor", "kritik hata", kind=PerceptKind.ALERT)   # salience 0.9 ≥ eşik
    d.perceive("owner", "monitor", "rutin ölçüm", kind=PerceptKind.METRIC)  # 0.4 < eşik
    att = d.attention("owner")
    assert len(att) == 1 and att[0]["content"] == "kritik hata"
    assert any(e["type"] == PerceiveEvents.ATTENTION for e in bus.history())


# ---- INTEGRATION: kayıpsızlık (yönlendirme sink'i yoksa bile percept kalıcı) ----
def test_lossless_without_sinks():
    d, _m, _c, _b = _build(memory=False, cognitive=False)
    p = d.perceive("owner", "s", "izole sinyal", kind=PerceptKind.OBSERVATION, subject="x")
    assert p["routed"] == []                              # sink yok
    assert d.explain("owner", p["id"])["content"] == "izole sinyal"   # yine de kalıcı


# ---- INTEGRATION: recent + stats + contract ----
def test_recent_stats_contract(pcd):
    d, _m, _c, _b = pcd
    d.perceive("owner", "s", "a", kind=PerceptKind.EVENT)
    d.perceive("owner", "s", "b", kind=PerceptKind.ALERT)
    assert len(d.recent("owner", kind=PerceptKind.ALERT)) == 1
    with pytest.raises(NotFoundError):
        d.explain("owner", "yok-id")
    s = d.stats()
    assert s["total"] == 2 and s["alerts"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "perception" and "perceive" in c["operations"]


# ---- SMOKE: boot() → uçtan uca (E5 + Memory birlikte) ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    p = mio.perception.perceive("owner", "rakip-izleme", "rakip fiyat düşürdü",
                                kind=PerceptKind.OBSERVATION, subject="rekabet", valence=-0.5)
    assert "cognitive" in p["routed"] and "memory" in p["routed"]       # her iki sink de bağlı
    assert any(b.subject == "rekabet" for b in mio.cognitive.beliefs())  # E5'e işlendi
    alert = mio.perception.perceive("owner", "sistem", "sunucu düştü", kind=PerceptKind.ALERT)
    assert alert["id"] in [a["id"] for a in mio.perception.attention("owner")]
    assert mio.perception.contract()["version"] == "1.0.0"
    mio.close()
