"""MIO Core · Model Management Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

**Anayasa gereği model seçimi DETERMİNİSTİK bir politikadır; LLM yalnız danışmandır, karar verici DEĞİL.**
Çekirdek: model registry + sürüm + **yaşam-döngüsü durum makinesi** (registered→available→deprecated→retired) +
**deterministik seçim politikası** (priority/context/cost) + sağlayıcı connector routing. Gerçek indirme/serve
enjekte edilen provider adapter'a (DI) delege; provider yoksa DÜRÜSTÇE no_connector — model `available` OLMAZ
(uydurma sonuç YOK — Madde 8). Model **çalıştırma** çekirdekte YOK. Model **emekliye ayırma** (retire) yetenek
kaybı olduğundan ONAY ister (Madde 24; owner/Executive)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModelKind:
    LLM = "llm"
    EMBEDDING = "embedding"
    VISION = "vision"
    SPEECH = "speech"
    RERANK = "rerank"
    ALL = {LLM, EMBEDDING, VISION, SPEECH, RERANK}


class Location:
    LOCAL = "local"             # yerel host (örn. Ollama)
    REMOTE = "remote"           # sağlayıcı API (örn. OpenAI/DeepSeek)
    HOSTED = "hosted"           # kendi barındırdığımız uzak servis
    ALL = {LOCAL, REMOTE, HOSTED}


class Lifecycle:
    REGISTERED = "registered"   # kayıtlı ama henüz sağlanmadı (provision edilmedi)
    AVAILABLE = "available"     # sağlandı, seçilebilir
    DEPRECATED = "deprecated"   # kullanımdan kaldırılıyor, seçim dışı
    RETIRED = "retired"         # emekli, kalıcı olarak devre dışı
    ALL = {REGISTERED, AVAILABLE, DEPRECATED, RETIRED}


# Deterministik yaşam-döngüsü geçişleri (izinli hedefler)
TRANSITIONS = {
    Lifecycle.REGISTERED: {Lifecycle.AVAILABLE, Lifecycle.RETIRED},
    Lifecycle.AVAILABLE: {Lifecycle.DEPRECATED, Lifecycle.RETIRED},
    Lifecycle.DEPRECATED: {Lifecycle.AVAILABLE, Lifecycle.RETIRED},   # yeniden etkinleştirilebilir
    Lifecycle.RETIRED: set(),                                         # terminal
}


class ModelMgmtError(Exception):
    """Model Management Domain temel hatası."""


class ValidationError(ModelMgmtError):
    pass


class UnauthorizedError(ModelMgmtError):
    pass


class NotFoundError(ModelMgmtError):
    pass


class TransitionError(ModelMgmtError):
    pass


@dataclass
class Model:
    name: str
    kind: str = ModelKind.LLM
    provider: str = ""
    location: str = Location.REMOTE
    version: str = "1.0.0"
    context_window: int = 0
    cost_per_1k: float = 0.0        # 1000 token başına maliyet (deterministik seçimde kullanılır)
    priority: int = 100            # yüksek = tercih edilir (operatör politikası)
    description: str = ""
    status: str = Lifecycle.REGISTERED
    endpoint: str = ""              # provision sonrası provider'ın döndürdüğü erişim ucu
    connector: str = ""            # sağlayan provider adapter adı
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "provider": self.provider,
                "location": self.location, "version": self.version, "context_window": self.context_window,
                "cost_per_1k": self.cost_per_1k, "priority": self.priority, "description": self.description,
                "status": self.status, "endpoint": self.endpoint, "connector": self.connector,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Model":
        return cls(name=d["name"], kind=d.get("kind", ModelKind.LLM), provider=d.get("provider", ""),
                   location=d.get("location", Location.REMOTE), version=d.get("version", "1.0.0"),
                   context_window=int(d.get("context_window", 0)), cost_per_1k=float(d.get("cost_per_1k", 0.0)),
                   priority=int(d.get("priority", 100)), description=d.get("description", ""),
                   status=d.get("status", Lifecycle.REGISTERED), endpoint=d.get("endpoint", ""),
                   connector=d.get("connector", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now())


def selection_score(m: Model) -> tuple:
    """Deterministik seçim skoru (LLM'siz). Sıra: priority↑, context_window↑, cost↓, name (kararlı tie-break)."""
    return (m.priority, m.context_window, -m.cost_per_1k, m.name)


@dataclass
class ModelMgmtConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering", "Reasoning", "Planning", "Perception"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Engineering"})
    # Madde 24: emekliye ayırma (yetenek kaybı) yalnız bunlarca
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "ModelKind", "Location", "Lifecycle", "TRANSITIONS", "Model", "ModelMgmtConfig", "selection_score",
    "ModelMgmtError", "ValidationError", "UnauthorizedError", "NotFoundError", "TransitionError",
]
