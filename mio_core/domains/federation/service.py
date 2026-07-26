"""MIO Core · Federation Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

**Anayasa: egemenlik/gizlilik korunur; dış düğümle paylaşım ONAY ister (Madde 24) ve DETERMİNİSTİK scope sınırıyla
kısıtlanır.** Peer registry + **deterministik federasyon politikası** (host allowlist + izinli scope) + güven durum
makinesi + paylaşım job durum makinesi. Gerçek uzak düğüm çağrısı enjekte edilen transport adapter'a (DI) delege;
yoksa **no_connector** (uydurma sonuç YOK — Madde 8). Gerçek ağ/uzak yürütme çekirdekte YOK. authz · validation ·
events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .contract import CONTRACT_VERSION, FederationEvents, federation_contract
from .models import (
    FederationConfig,
    NotFoundError,
    PEER_TRANSITIONS,
    Peer,
    PeerStatus,
    ShareJob,
    ShareStatus,
    TransitionError,
    TrustLevel,
    UnauthorizedError,
    ValidationError,
)
from .repository import FederationRepository

logger = logging.getLogger("mio.domain.federation")

Transport = Callable[[dict], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FederationDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: FederationRepository, *, bus=None,
                 config: Optional[FederationConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or FederationConfig()
        self._transport: Optional[tuple[Transport, str]] = None   # tek uzak transport adapter (DI)
        self._metrics = {"peers": 0, "trusted": 0, "rejected": 0, "revoked": 0, "shares": 0,
                         "shared": 0, "no_connector": 0, "failed": 0, "approval_required": 0}

    # ------------------------------------------------------------------ #
    def register_transport(self, fn: Transport, *, name: str = "adapter") -> None:
        """GERÇEK uzak düğüm transport connector'ı bağlar (kompozisyon-zamanı DI)."""
        self._transport = (fn, name)

    def register_peer(self, actor: str, name: str, *, endpoint: str = "",
                      capabilities: Optional[list] = None, trust_level: str = TrustLevel.NONE,
                      description: str = "") -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "peer adı")
        if trust_level not in TrustLevel.ALL:
            raise ValidationError(f"Geçersiz güven seviyesi: {trust_level}")
        p = Peer(name=name, endpoint=endpoint, capabilities=list(capabilities or []),
                 trust_level=trust_level, description=description, status=PeerStatus.REGISTERED)
        self._repo.put_peer(p)
        self._metrics["peers"] += 1
        self._emit(FederationEvents.PEER_REGISTERED, {"actor": actor, "id": p.id})
        return p.to_dict()

    def trust_peer(self, actor: str, peer_id: str, *, trust_level: str = TrustLevel.BASIC) -> dict[str, Any]:
        """Peer'ı güvenilir kılar (Madde 24; approver). Host allowlist'te DEĞİLSE otomatik reddedilir."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' peer güvenilir kılamaz (Madde 24)")
        if trust_level not in TrustLevel.ALL:
            raise ValidationError(f"Geçersiz güven seviyesi: {trust_level}")
        p = self._require_peer(peer_id)
        if not self._cfg.host_trusted(p.endpoint):   # allowlist dışı → egemenlik gereği reddedilir
            self._set_peer_status(p, PeerStatus.REVOKED)
            p.rejected_reason = "untrusted_host"
            self._repo.put_peer(p)
            self._metrics["rejected"] += 1
            self._emit(FederationEvents.PEER_REJECTED, {"id": p.id, "reason": "untrusted_host"})
            return {"trusted": False, "status": p.status, "reason": "untrusted_host", "peer": p.to_dict()}
        self._set_peer_status(p, PeerStatus.TRUSTED)
        p.trust_level = trust_level
        p.approved_by = actor
        self._repo.put_peer(p)
        self._metrics["trusted"] += 1
        self._emit(FederationEvents.PEER_TRUSTED, {"id": p.id, "by": actor, "trust_level": trust_level})
        return {"trusted": True, "status": p.status, "peer": p.to_dict()}

    def revoke_peer(self, actor: str, peer_id: str) -> dict[str, Any]:
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' peer güvenini kaldıramaz (Madde 24)")
        p = self._require_peer(peer_id)
        self._set_peer_status(p, PeerStatus.REVOKED)
        self._repo.put_peer(p)
        self._metrics["revoked"] += 1
        self._emit(FederationEvents.PEER_REVOKED, {"id": p.id})
        return p.to_dict()

    def share(self, actor: str, peer_id: str, scope: str, *, payload: Optional[dict] = None,
              user_approved: bool = False) -> dict[str, Any]:
        """Dış paylaşım isteği. Yalnız TRUSTED peer + izinli scope. Onaysız → requires_approval (Madde 24)."""
        self._authorize_writer(actor)
        p = self._require_peer(peer_id)
        scope = self._require(scope, "scope")
        if p.status != PeerStatus.TRUSTED:
            raise ValidationError(f"Yalnız 'trusted' peer'a paylaşım yapılır (durum: {p.status})")
        if not self._cfg.scope_allowed(scope):       # egemenlik sınırı (deterministik)
            raise ValidationError(f"İzin verilmeyen paylaşım kapsamı: {scope}")
        job = ShareJob(peer_id=peer_id, scope=scope, payload=dict(payload or {}), status=ShareStatus.PENDING)
        self._metrics["shares"] += 1
        self._emit(FederationEvents.SHARE_REQUESTED, {"id": job.id, "peer_id": peer_id, "scope": scope})

        if not user_approved:                        # Madde 24: dış paylaşım onaysız gönderilmez
            job.status = ShareStatus.REQUIRES_APPROVAL
            self._repo.put_share(job)
            self._metrics["approval_required"] += 1
            self._emit(FederationEvents.APPROVAL_REQUIRED, {"id": job.id, "scope": scope})
            return job.to_dict()
        return self._dispatch(job, p)

    def approve_share(self, actor: str, share_id: str) -> dict[str, Any]:
        """Onay bekleyen dış paylaşımı onaylar ve gönderir (yalnız approver — Madde 24)."""
        if not self._cfg.is_approver(actor):
            raise UnauthorizedError(f"'{actor}' dış paylaşım onaylayamaz (Madde 24)")
        job = self._repo.get_share(share_id)
        if job is None:
            raise NotFoundError(f"Paylaşım bulunamadı: {share_id}")
        if job.status != ShareStatus.REQUIRES_APPROVAL:
            raise ValidationError(f"Yalnız 'requires_approval' onaylanır (durum: {job.status})")
        peer = self._require_peer(job.peer_id)
        if peer.status != PeerStatus.TRUSTED:        # onay anında peer güveni yeniden doğrulanır
            raise ValidationError(f"Peer artık 'trusted' değil (durum: {peer.status})")
        job.approved_by = actor
        self._emit(FederationEvents.SHARE_APPROVED, {"id": share_id, "by": actor})
        return self._dispatch(job, peer)

    def _dispatch(self, job: ShareJob, peer: Peer) -> dict[str, Any]:
        if self._transport is None:                 # DÜRÜST: gerçek transport bağlı değil
            job.status = ShareStatus.NO_CONNECTOR
            job.finished_at = _now()
            self._repo.put_share(job)
            self._metrics["no_connector"] += 1
            self._emit(FederationEvents.NO_CONNECTOR, {"id": job.id, "peer_id": peer.id})
            return job.to_dict()
        fn, name = self._transport
        job.connector = name
        try:
            result = fn({"peer": peer.to_dict(), "scope": job.scope, "payload": job.payload})
            job.status = ShareStatus.SHARED
            job.result = dict(result or {})
            self._metrics["shared"] += 1
            self._emit(FederationEvents.SHARED, {"id": job.id, "peer_id": peer.id})
        except Exception as exc:  # noqa: BLE001 — transport hatası işe dönüşür, sistemi bozmaz
            job.status = ShareStatus.FAILED
            job.error = str(exc)[:300]
            self._metrics["failed"] += 1
            self._emit(FederationEvents.SHARE_FAILED, {"id": job.id, "error": job.error})
        job.finished_at = _now()
        self._repo.put_share(job)
        return job.to_dict()

    # -- sorgular -------------------------------------------------------- #
    def get_peer(self, actor: str, peer_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_peer(peer_id).to_dict()

    def list_peers(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in PeerStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [p.to_dict() for p in self._repo.all_peers(status=status)]

    def get_share(self, actor: str, share_id: str) -> dict[str, Any]:
        self._authorize(actor)
        s = self._repo.get_share(share_id)
        if s is None:
            raise NotFoundError(f"Paylaşım bulunamadı: {share_id}")
        return s.to_dict()

    def list_shares(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if status is not None and status not in ShareStatus.ALL:
            raise ValidationError(f"Geçersiz durum: {status}")
        return [s.to_dict() for s in self._repo.all_shares(status=status)]

    def scopes(self, actor: str) -> dict[str, Any]:
        self._authorize(actor)
        return {"allowed": sorted(self._cfg.allowed_scopes), "trusted_hosts": sorted(self._cfg.trusted_hosts),
                "transport": self._transport[1] if self._transport else None}

    def stats(self) -> dict[str, Any]:
        return {"peers": self._repo.peer_count(), "trusted_peers": self._repo.peer_count(status=PeerStatus.TRUSTED),
                "shares": self._repo.share_count(),
                "pending_approval": self._repo.share_count(status=ShareStatus.REQUIRES_APPROVAL),
                "transport": bool(self._transport), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return federation_contract()

    # ------------------------------------------------------------------ #
    def _set_peer_status(self, p: Peer, target: str) -> None:
        if target != p.status and target not in PEER_TRANSITIONS.get(p.status, set()):
            raise TransitionError(f"Geçersiz peer geçişi: {p.status} → {target}")
        p.status = target
        p.updated_at = _now()

    def _require_peer(self, peer_id: str) -> Peer:
        p = self._repo.get_peer(peer_id)
        if p is None:
            raise NotFoundError(f"Peer bulunamadı: {peer_id}")
        return p

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' federation erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' federation yönetimi için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
