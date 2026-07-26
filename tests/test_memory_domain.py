"""MIO Core · Memory Domain (Faz 1 · Domain 2) — üretim testleri: unit + integration + smoke.

Placeholder/mock YOK; gerçek SQLite repository + deterministik yaşam-döngüsü üzerinden. Validation,
authorization, WM sınırı/çıkarma, konsolidasyon (STM→LTM, epizodik→semantik), çürüme/buda, geri çağırma,
events ve uçtan-uca akış doğrulanır."""

import pytest

from mio_core.domains.memory import (
    MemoryConfig,
    MemoryDomain,
    MemoryRepository,
    MemoryType,
    MemEvents,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(config: MemoryConfig | None = None):
    repo = MemoryRepository(":memory:")
    bus = EventBus(record=True)
    dom = MemoryDomain(repo, bus=bus, config=config or MemoryConfig())
    return dom, repo, bus


@pytest.fixture
def mem():
    return _build()


# ---- UNIT: validation ----
def test_remember_validation(mem):
    d, _r, _b = mem
    with pytest.raises(ValidationError):
        d.remember("owner", "   ")                       # boş içerik
    with pytest.raises(ValidationError):
        d.remember("owner", "geçerli", mtype="uydurma")  # geçersiz tip


def test_importance_clamped(mem):
    d, _r, _b = mem
    hi = d.remember("owner", "önemli", importance=9.0)
    lo = d.remember("owner", "önemsiz", importance=-3.0)
    assert hi.importance == 1.0 and lo.importance == 0.0


# ---- UNIT: authorization ----
def test_authorization_rules(mem):
    d, _r, _b = mem
    with pytest.raises(UnauthorizedError):
        d.remember("yabanci", "içerik")                  # kayıtsız aktör
    with pytest.raises(UnauthorizedError):
        d.recall("yabanci", "sorgu")
    assert d.remember("Executive", "yetkili brain").id   # yetkili aktör geçer


# ---- UNIT: store + event ----
def test_remember_persists_and_emits(mem):
    d, repo, bus = mem
    item = d.remember("owner", "ilk anı", mtype=MemoryType.EPISODIC, tags=["giris"])
    assert repo.get(item.id) is not None
    assert any(e["type"] == MemEvents.STORED for e in bus.history())


# ---- UNIT: WM sınırı + çıkarma ----
def test_working_memory_capacity_evicts(mem):
    d, repo, bus = mem                                    # wm_capacity=7
    for i in range(9):
        d.note_working("owner", f"wm-{i}")
    wm = repo.list(MemoryType.WORKING)
    assert len(wm) < 9 and len(wm) <= MemoryConfig().wm_capacity
    assert any(e["type"] == MemEvents.WORKING_EVICTED for e in bus.history())


# ---- UNIT: forget + not found ----
def test_forget_and_not_found(mem):
    d, repo, bus = mem
    item = d.remember("owner", "silinecek")
    d.forget("owner", item.id)
    assert repo.get(item.id) is None
    assert any(e["type"] == MemEvents.FORGOTTEN for e in bus.history())
    with pytest.raises(NotFoundError):
        d.forget("owner", "yok-boyle-id")


# ---- INTEGRATION: geri çağırma + pekiştirme ----
def test_recall_scores_and_reinforces(mem):
    d, repo, _b = mem
    hit = d.remember("owner", "gelir artışı için içerik takvimi", tags=["gelir"])
    d.remember("owner", "tamamen alakasız kayıt", tags=["baska"])
    d.consolidate("owner")                                         # epizodik çürür: 1.0→0.9
    weakened = repo.get(hit.id).strength
    assert weakened < 1.0
    results = d.recall("owner", "gelir içerik")
    assert results and results[0]["content"] == hit.content        # skorlama isabetli
    assert repo.get(hit.id).access_count == 1                       # erişim sayacı arttı
    assert repo.get(hit.id).strength > weakened                    # erişim pekiştirdi (geri kazanım)


# ---- INTEGRATION: konsolidasyon STM→LTM + epizodik→semantik ----
def test_consolidation_promotes_and_derives(mem):
    d, repo, bus = mem
    d.remember("owner", "önemli kısa vadeli", mtype=MemoryType.SHORT_TERM, importance=0.9)
    d.remember("owner", "önemsiz kısa vadeli", mtype=MemoryType.SHORT_TERM, importance=0.2)
    d.remember("owner", "deneyim 1", mtype=MemoryType.EPISODIC, tags=["pazarlama"])
    d.remember("owner", "deneyim 2", mtype=MemoryType.EPISODIC, tags=["pazarlama"])
    res = d.consolidate("owner")
    assert res["promoted_to_ltm"] == 1                             # yalnızca yüksek önem terfi
    assert repo.count(MemoryType.LONG_TERM) == 1
    assert res["semantic_created"] == 1                            # tekrarlanan etiket → örüntü
    assert any(it.tags == ["pazarlama"] for it in repo.list(MemoryType.SEMANTIC))
    assert any(e["type"] == MemEvents.CONSOLIDATED for e in bus.history())


# ---- INTEGRATION: çürüme/buda durable katmanları korur ----
def test_decay_prunes_weak_but_keeps_durable():
    cfg = MemoryConfig(decay_rate=0.9, prune_below=0.5)           # agresif çürüme
    d, repo, _b = _build(cfg)
    weak = d.remember("owner", "zayıf epizot", mtype=MemoryType.EPISODIC)
    durable = d.remember("owner", "kalıcı bilgi", mtype=MemoryType.SEMANTIC)
    d.consolidate("owner")
    assert repo.get(weak.id) is None                              # 1.0*0.1=0.1 < 0.5 → budandı
    assert repo.get(durable.id) is not None                       # durable korunur


# ---- INTEGRATION: stats + contract ----
def test_stats_and_contract(mem):
    d, _r, _b = mem
    d.remember("owner", "a", mtype=MemoryType.EPISODIC)
    d.remember("owner", "b", mtype=MemoryType.LONG_TERM)
    s = d.stats()
    assert s["total"] == 2 and s["episodic"] == 1 and s["stored"] == 2
    assert s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "memory" and c["version"] == "1.0.0" and "recall" in c["operations"]


# ---- SMOKE: boot() → domain uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    item = mio.memory.remember("owner", "aylık gelir hedefi 5000$", tags=["gelir"])
    hits = mio.memory.recall("owner", "gelir hedefi")
    assert hits and hits[0]["id"] == item.id
    mio.memory.remember("owner", "yüksek önemli STM", mtype=MemoryType.SHORT_TERM, importance=0.9)
    assert mio.memory.consolidate("owner")["promoted_to_ltm"] == 1
    assert mio.memory.stats()["total"] >= 2
    assert mio.memory.contract()["version"] == "1.0.0"
    mio.close()
