"""MIO Core · Autonomous Operations Domain (Faz 5 · Domain 41) — üretim testleri: unit+integration+smoke.

Anayasa özü (EN HASSAS): **otonom aksiyon KARAR VERMEZ; Executive'e ÖNERİ üretir; uygulama Madde 24 onayıyla.**
Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik action üzerinden. Deterministik tetik,
öneri→onay akışı, kapalı-döngü YALNIZ allowlist+opt-in, DÜRÜST no_connector, action hatası, events doğrulanır."""

import pytest

from mio_core.domains.autonomous_ops import (
    AutoOpsConfig,
    AutoOpsEvents,
    AutoOpsRepository,
    AutonomousOperationsDomain,
    NotFoundError,
    ProposalStatus,
    Severity,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(config=None):
    repo = AutoOpsRepository(":memory:")
    bus = EventBus(record=True)
    dom = AutonomousOperationsDomain(repo, bus=bus, config=config)
    return dom, repo, bus


@pytest.fixture
def ao():
    return _build()


# ---- UNIT: validation + authz ----
def test_validation_authz(ao):
    d, _r, _b = ao
    with pytest.raises(UnauthorizedError):
        d.add_rule("Reasoning", "r", "cpu", ">", 90.0, "scale_out")   # reader ama writer değil
    with pytest.raises(ValidationError):
        d.add_rule("owner", "r", "cpu", "??", 90.0, "scale_out")      # geçersiz karşılaştırıcı
    with pytest.raises(ValidationError):
        d.add_rule("owner", "r", "cpu", ">", 90.0, "scale_out", severity="uydurma")


# ---- INTEGRATION: deterministik tetik → ÖNERİ (karar DEĞİL, Madde 24) ----
def test_trigger_produces_recommendation_not_decision(ao):
    d, _r, bus = ao
    d.add_rule("owner", "cpu yüksek", "cpu", ">", 90.0, "scale_out", severity=Severity.CRITICAL)
    # eşik altı → öneri yok
    assert d.observe("owner", "cpu", 50.0) == []
    # eşik aşıldı → ÖNERİ üretilir ama YÜRÜTÜLMEZ (requires_approval)
    props = d.observe("owner", "cpu", 95.0)
    assert len(props) == 1 and props[0]["status"] == ProposalStatus.REQUIRES_APPROVAL
    assert props[0]["action"] == "scale_out" and props[0]["auto"] is False
    assert any(e["type"] == AutoOpsEvents.PROPOSAL_CREATED for e in bus.history())
    # kapalı-döngü açık değil → hiçbir şey auto-execute olmadı
    assert d.stats()["auto_executed"] == 0


# ---- INTEGRATION: öneri → Madde 24 onay → uygulama ----
def test_approve_proposal_executes(ao):
    d, _r, bus = ao
    d.register_action("scale_out", lambda ctx: {"scaled": True}, name="k8s-adapter")
    d.add_rule("owner", "r", "cpu", ">", 90.0, "scale_out")
    prop = d.observe("owner", "cpu", 99.0)[0]
    with pytest.raises(UnauthorizedError):
        d.approve_proposal("Engineering", prop["id"])       # approver değil
    done = d.approve_proposal("owner", prop["id"])
    assert done["status"] == ProposalStatus.EXECUTED and done["approved_by"] == "owner"
    assert done["result"] == {"scaled": True}
    assert any(e["type"] == AutoOpsEvents.EXECUTED for e in bus.history())


# ---- INTEGRATION: reddedilen öneri uygulanmaz ----
def test_reject_proposal(ao):
    d, _r, _b = ao
    d.add_rule("owner", "r", "err", ">", 5.0, "rollback")
    prop = d.observe("owner", "err", 9.0)[0]
    rej = d.reject_proposal("owner", prop["id"], reason="beklenen dalgalanma")
    assert rej["status"] == ProposalStatus.REJECTED and rej["rejected_reason"] == "beklenen dalgalanma"
    with pytest.raises(ValidationError):
        d.approve_proposal("owner", prop["id"])             # artık requires_approval değil


# ---- INTEGRATION: kapalı-döngü YALNIZ allowlist + opt-in ----
def test_closed_loop_only_allowlisted_and_optin():
    cfg = AutoOpsConfig()
    cfg.closed_loop_enabled = True
    cfg.safe_actions.add("clear_cache")                     # yalnız bu aksiyon güvenli-allowlist
    d, _r, bus = _build(config=cfg)
    d.register_action("clear_cache", lambda ctx: {"cleared": True})
    d.add_rule("owner", "cache", "cache_miss", ">", 0.8, "clear_cache")
    d.add_rule("owner", "restart", "cache_miss", ">", 0.8, "restart_service")  # allowlist DIŞI
    props = {p["action"]: p for p in d.observe("owner", "cache_miss", 0.95)}
    # allowlisted güvenli → otomatik yürütüldü
    assert props["clear_cache"]["status"] == ProposalStatus.EXECUTED and props["clear_cache"]["auto"] is True
    # allowlist dışı → yine öneri kalır (onaysız yürütülmez)
    assert props["restart_service"]["status"] == ProposalStatus.REQUIRES_APPROVAL
    assert any(e["type"] == AutoOpsEvents.AUTO_EXECUTED for e in bus.history())


# ---- INTEGRATION: action adapter yoksa DÜRÜST no_connector; hata → failed ----
def test_no_connector_and_failure(ao):
    d, _r, bus = ao
    d.add_rule("owner", "r", "disk", ">", 90.0, "expand_disk")
    p = d.observe("owner", "disk", 95.0)[0]
    # adapter yok → onaylanınca dürüst no_connector
    res = d.approve_proposal("owner", p["id"])
    assert res["status"] == ProposalStatus.NO_CONNECTOR
    assert any(e["type"] == AutoOpsEvents.NO_CONNECTOR for e in bus.history())
    # action hatası → failed
    d.register_action("expand_disk", lambda ctx: (_ for _ in ()).throw(RuntimeError("kota aşıldı")))
    p2 = d.observe("owner", "disk", 96.0)[0]
    fail = d.approve_proposal("owner", p2["id"])
    assert fail["status"] == ProposalStatus.FAILED and "kota aşıldı" in fail["error"]


# ---- INTEGRATION: rules + stats + contract ----
def test_rules_stats_contract(ao):
    d, _r, _b = ao
    d.add_rule("owner", "r1", "lat", ">", 200.0, "alert")
    d.observe("owner", "lat", 300.0)
    assert len(d.list_rules("owner")) == 1
    assert len(d.list_proposals("owner", status=ProposalStatus.REQUIRES_APPROVAL)) == 1
    s = d.stats()
    assert s["rules"] == 1 and s["pending_approval"] == 1 and s["closed_loop_enabled"] is False
    assert s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "autonomous_operations" and "approve_proposal" in c["operations"]
    with pytest.raises(NotFoundError):
        d.get_proposal("owner", "yok")


# ---- SMOKE: boot() → öneri (karar değil) + Madde 24 uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    aops = mio.autonomous_operations
    aops.add_rule("owner", "hata oranı", "error_rate", ">=", 0.1, "rollback", severity=Severity.CRITICAL)
    props = aops.observe("owner", "error_rate", 0.25)
    # otonom aksiyon KARAR VERMEDİ; Executive onayı bekleyen ÖNERİ üretti (varsayılan kapalı-döngü kapalı)
    assert len(props) == 1 and props[0]["status"] == ProposalStatus.REQUIRES_APPROVAL
    assert aops.stats()["auto_executed"] == 0
    assert aops.contract()["version"] == "1.0.0"
    mio.close()
