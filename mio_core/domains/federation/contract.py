"""MIO Core · Federation Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class FederationEvents:
    PEER_REGISTERED = "federation.peer_registered"
    PEER_TRUSTED = "federation.peer_trusted"
    PEER_REJECTED = "federation.peer_rejected"
    PEER_REVOKED = "federation.peer_revoked"
    SHARE_REQUESTED = "federation.share_requested"
    APPROVAL_REQUIRED = "federation.approval_required"
    SHARE_APPROVED = "federation.share_approved"
    SHARED = "federation.shared"
    SHARE_FAILED = "federation.share_failed"
    NO_CONNECTOR = "federation.no_connector"


OPERATIONS = ("register_peer", "trust_peer", "revoke_peer", "share", "approve_share",
              "get_peer", "list_peers", "get_share", "list_shares", "scopes", "stats")


def federation_contract() -> dict[str, Any]:
    return {
        "domain": "federation",
        "version": CONTRACT_VERSION,
        "description": "Eş (peer) düğüm registry + DETERMİNİSTİK federasyon politikası (host allowlist + izinli "
                       "paylaşım kapsamı) + güven durum makinesi + paylaşım job durum makinesi. Dış düğümle "
                       "paylaşım onay ister (Madde 24) ve scope sınırıyla kısıtlanır (egemenlik/gizlilik). "
                       "Gerçek uzak çağrı adapter'a delege; yoksa no_connector.",
        "operations": list(OPERATIONS),
        "events": [FederationEvents.PEER_REGISTERED, FederationEvents.PEER_TRUSTED,
                   FederationEvents.PEER_REJECTED, FederationEvents.PEER_REVOKED,
                   FederationEvents.SHARE_REQUESTED, FederationEvents.APPROVAL_REQUIRED,
                   FederationEvents.SHARE_APPROVED, FederationEvents.SHARED,
                   FederationEvents.SHARE_FAILED, FederationEvents.NO_CONNECTOR],
        "peer_statuses": ["registered", "trusted", "revoked"],
        "share_statuses": ["pending", "requires_approval", "shared", "failed", "no_connector"],
        "policy": "deterministik: peer host allowlist + izinli scope (egemenlik sınırı)",
        "invariants": ["dış düğüm yalnız allowlist host ise güvenilir kılınabilir (aksi otomatik reddedilir)",
                       "yalnız TRUSTED peer'a paylaşım yapılır",
                       "yalnız izinli scope paylaşılabilir (egemenlik/gizlilik sınırı — deterministik)",
                       "dış paylaşım onay ister (Madde 24; owner/Executive); onaysız gönderilmez",
                       "gerçek uzak çağrı adapter'a delege; yoksa no_connector (uydurma YOK — Madde 8)"],
    }
