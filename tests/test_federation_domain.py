"""MIO Core · Federation Domain (Faz 5 · Domain 39) — üretim testleri: unit+integration+smoke.

Anayasa özü: **egemenlik/gizlilik korunur; dış paylaşım ONAY ister (Madde 24) + DETERMİNİSTİK scope sınırı.**
Placeholder/mock YOK; gerçek SQLite + enjekte edilen deterministik transport üzerinden. Host allowlist güveni,
scope egemenlik sınırı, Madde 24 onay kapısı, DÜRÜST no_connector, transport hatası, events doğrulanır."""

import pytest

from mio_core.domains.federation import (
    FederationConfig,
    FederationDomain,
    FederationEvents,
    FederationRepository,
    NotFoundError,
    PeerStatus,
    ShareStatus,
    TrustLevel,
    UnauthorizedError,
    ValidationError,
)
from mio_core.events import EventBus


def _build(config=None):
    if config is None:
        config = FederationConfig()
        config.trusted_hosts.add("peer.mio.net")     # allowlist host
    repo = FederationRepository(":memory:")
    bus = EventBus(record=True)
    dom = FederationDomain(repo, bus=bus, config=config)
    return dom, repo, bus


@pytest.fixture
def fd():
    return _build()


def _trusted_peer(d, actor="owner", endpoint="https://peer.mio.net/api"):
    p = d.register_peer(actor, "Ortak Düğüm", endpoint=endpoint, capabilities=["knowledge"])
    d.trust_peer("owner", p["id"], trust_level=TrustLevel.FULL)
    return d.get_peer("owner", p["id"])


# ---- UNIT: validation + authz ----
def test_validation_authz(fd):
    d, _r, _b = fd
    with pytest.raises(UnauthorizedError):
        d.register_peer("Reasoning", "X")                 # reader ama writer değil
    with pytest.raises(ValidationError):
        d.register_peer("owner", "X", trust_level="uydurma")


# ---- INTEGRATION: allowlist dışı host güvenilir kılınamaz (otomatik red) ----
def test_untrusted_host_auto_rejected(fd):
    d, _r, bus = fd
    p = d.register_peer("owner", "Şüpheli", endpoint="https://evil.example.com/api")
    res = d.trust_peer("owner", p["id"])                  # host allowlist'te değil
    assert res["trusted"] is False and res["status"] == PeerStatus.REVOKED
    assert res["reason"] == "untrusted_host"
    assert any(e["type"] == FederationEvents.PEER_REJECTED for e in bus.history())


# ---- INTEGRATION: Madde 24 — yalnız approver güven verir ----
def test_only_approver_trusts(fd):
    d, _r, _b = fd
    p = d.register_peer("owner", "Ortak", endpoint="https://peer.mio.net/api")
    with pytest.raises(UnauthorizedError):
        d.trust_peer("Engineering", p["id"])              # writer ama approver değil
    res = d.trust_peer("owner", p["id"])
    assert res["trusted"] is True and res["status"] == PeerStatus.TRUSTED


# ---- INTEGRATION: paylaşım yalnız TRUSTED peer + izinli scope ----
def test_share_requires_trusted_and_allowed_scope(fd):
    d, _r, _b = fd
    # güvenilmez peer → paylaşım reddedilir
    reg = d.register_peer("owner", "Kayıtlı", endpoint="https://peer.mio.net/api")
    with pytest.raises(ValidationError):
        d.share("owner", reg["id"], "public_knowledge")   # henüz trusted değil
    peer = _trusted_peer(d)
    # izin verilmeyen scope → egemenlik sınırı reddeder
    with pytest.raises(ValidationError):
        d.share("owner", peer["id"], "private_secrets")


# ---- INTEGRATION: dış paylaşım → requires_approval (Madde 24) + transport ile gönderim ----
def test_share_requires_approval_then_dispatch(fd):
    d, _r, bus = fd
    sent = {}

    def transport(ctx):
        sent["scope"] = ctx["scope"]
        return {"ack": True}

    d.register_transport(transport, name="grpc-adapter")
    peer = _trusted_peer(d)
    job = d.share("Engineering", peer["id"], "aggregate_metrics")
    assert job["status"] == ShareStatus.REQUIRES_APPROVAL   # onaysız gönderilmez
    assert any(e["type"] == FederationEvents.APPROVAL_REQUIRED for e in bus.history())
    with pytest.raises(UnauthorizedError):
        d.approve_share("Engineering", job["id"])          # approver değil
    done = d.approve_share("owner", job["id"])             # owner onaylar → gönderilir
    assert done["status"] == ShareStatus.SHARED and done["approved_by"] == "owner"
    assert done["result"] == {"ack": True} and sent["scope"] == "aggregate_metrics"
    assert any(e["type"] == FederationEvents.SHARED for e in bus.history())


# ---- INTEGRATION: transport yoksa DÜRÜST no_connector; hata → failed ----
def test_no_connector_and_failure(fd):
    d, _r, bus = fd
    peer = _trusted_peer(d)
    # transport yok → önceden-onaylı paylaşım bile no_connector
    job = d.share("owner", peer["id"], "public_knowledge", user_approved=True)
    assert job["status"] == ShareStatus.NO_CONNECTOR
    assert any(e["type"] == FederationEvents.NO_CONNECTOR for e in bus.history())
    # transport hatası → failed
    d.register_transport(lambda ctx: (_ for _ in ()).throw(RuntimeError("ağ kopması")))
    job2 = d.share("owner", peer["id"], "public_knowledge", user_approved=True)
    assert job2["status"] == ShareStatus.FAILED and "ağ kopması" in job2["error"]


# ---- INTEGRATION: revoke + stats + contract ----
def test_revoke_stats_contract(fd):
    d, _r, _b = fd
    peer = _trusted_peer(d)
    d.share("owner", peer["id"], "public_knowledge")      # requires_approval
    rev = d.revoke_peer("owner", peer["id"])
    assert rev["status"] == PeerStatus.REVOKED
    with pytest.raises(NotFoundError):
        d.get_peer("owner", "yok")
    s = d.stats()
    assert s["peers"] == 1 and s["pending_approval"] == 1 and s["contract_version"] == "1.0.0"
    c = d.contract()
    assert c["domain"] == "federation" and "approve_share" in c["operations"]
    sc = d.scopes("owner")
    assert "aggregate_metrics" in sc["allowed"] and "peer.mio.net" in sc["trusted_hosts"]


# ---- SMOKE: boot() → allowlist + Madde 24 uçtan uca ----
def test_smoke_via_runtime(tmp_path):
    from mio_core.runtime import boot
    mio = boot(workspace=str(tmp_path / "mio"), connect_ollama=False, discover_hw=False)
    fed = mio.federation
    # varsayılan allowlist boş → hiçbir host güvenilir kılınamaz (egemenlik varsayılan-güvenli)
    p = fed.register_peer("owner", "DışDüğüm", endpoint="https://peer.mio.net/api")
    res = fed.trust_peer("owner", p["id"])
    assert res["trusted"] is False and res["reason"] == "untrusted_host"
    assert fed.contract()["version"] == "1.0.0"
    mio.close()
