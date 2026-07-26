"""MIO Core · Perception Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Dış sinyalleri tipli PERCEPT'lere normalize eder ve bilişe yönlendirir: OBSERVATION+subject → E5 belief
(inanç oluşumu, çelişki E5'te ele alınır), her percept → Memory epizodik (best-effort), yüksek belirginlik →
Attention tetiği. Percept her hâlükârda kendi deposuna yazılır (yönlendirme başarısız olsa bile kayıp yok).
authorization · validation · events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .contract import CONTRACT_VERSION, PerceiveEvents, perception_contract
from .models import (
    DEFAULT_SALIENCE,
    NotFoundError,
    Percept,
    PerceptKind,
    PerceptionConfig,
    UnauthorizedError,
    ValidationError,
)
from .repository import PerceptionRepository

logger = logging.getLogger("mio.domain.perception")


class PerceptionDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: PerceptionRepository, *, memory=None, cognitive=None, bus=None,
                 config: Optional[PerceptionConfig] = None) -> None:
        self._repo = repository
        self._memory = memory          # MemoryDomain (opsiyonel) — epizodik kayıt
        self._cognitive = cognitive    # E5 CognitiveEngine (opsiyonel) — inanç oluşumu
        self._bus = bus
        self._cfg = config or PerceptionConfig()
        self._metrics = {"perceived": 0, "attention": 0, "to_memory": 0, "to_cognitive": 0}

    # ------------------------------------------------------------------ #
    def perceive(self, actor: str, source: str, content: str, *, kind: str = PerceptKind.SIGNAL,
                 subject: str = "", valence: float = 0.0, salience: Optional[float] = None,
                 tags: Optional[list] = None) -> dict[str, Any]:
        """Bir dış sinyali normalize eder, bilişe yönlendirir ve kalıcılaştırır."""
        self._authorize_writer(actor)
        source = self._require(source, "kaynak (source)")
        content = self._require(content, "içerik (content)")
        if kind not in PerceptKind.ALL:
            raise ValidationError(f"Geçersiz percept türü: {kind}")
        sal = self._clamp(DEFAULT_SALIENCE.get(kind, 0.5) if salience is None else salience)
        percept = Percept(source=source, kind=kind, content=content, subject=subject.strip(),
                          valence=self._clamp_signed(valence), salience=sal,
                          tags=list(tags or []), actor=actor)
        self._route(percept)
        self._repo.put(percept)                        # yönlendirmeden SONRA (routed dolu) — kayıp yok
        self._metrics["perceived"] += 1
        self._emit(PerceiveEvents.PERCEIVED, {"actor": actor, "id": percept.id, "kind": kind,
                                              "salience": sal})
        if sal >= self._cfg.attention_threshold:
            self._metrics["attention"] += 1
            self._emit(PerceiveEvents.ATTENTION, {"id": percept.id, "salience": sal, "content": content})
        return percept.to_dict()

    def recent(self, actor: str, *, limit: Optional[int] = None,
               kind: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in PerceptKind.ALL:
            raise ValidationError(f"Geçersiz percept türü: {kind}")
        n = min(int(limit or self._cfg.history_limit), self._cfg.history_limit)
        return [p.to_dict() for p in self._repo.recent(n, kind=kind)]

    def attention(self, actor: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Dikkat gerektiren (yüksek belirginlik) percept'ler."""
        self._authorize(actor)
        return [p.to_dict() for p in self._repo.high_salience(self._cfg.attention_threshold, limit=limit)]

    def explain(self, actor: str, percept_id: str) -> dict[str, Any]:
        self._authorize(actor)
        p = self._repo.get(percept_id)
        if p is None:
            raise NotFoundError(f"Percept bulunamadı: {percept_id}")
        return p.to_dict()

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"total": self._repo.count(),
                "alerts": self._repo.count(PerceptKind.ALERT),
                "observations": self._repo.count(PerceptKind.OBSERVATION),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return perception_contract()

    # ------------------------------------------------------------------ #
    def _route(self, percept: Percept) -> None:
        # 1) Gözlem + konu → E5 inanç oluşumu (çelişki E5'te 1. sınıf)
        if (self._cfg.route_to_cognitive and self._cognitive is not None
                and percept.kind == PerceptKind.OBSERVATION and percept.subject):
            try:
                self._cognitive.observe(percept.subject, percept.content, source="perception",
                                        valence=percept.valence,
                                        confidence=round(0.5 + 0.4 * percept.salience, 3))
                percept.routed.append("cognitive")
                self._metrics["to_cognitive"] += 1
                self._emit(PerceiveEvents.ROUTED, {"id": percept.id, "sink": "cognitive"})
            except Exception as exc:  # noqa: BLE001 — yönlendirme best-effort, percept kaybolmaz
                logger.warning("Perception→Cognitive yönlendirme atlandı: %s", exc)
        # 2) Deneyim → epizodik bellek (best-effort; yetki/erişim başarısız olabilir)
        if self._cfg.route_to_memory and self._memory is not None:
            try:
                self._memory.remember(self._cfg.memory_actor, f"[{percept.kind}] {percept.content}",
                                      mtype="episodic", importance=percept.salience,
                                      tags=percept.tags + [percept.source], source="perception")
                percept.routed.append("memory")
                self._metrics["to_memory"] += 1
                self._emit(PerceiveEvents.ROUTED, {"id": percept.id, "sink": "memory"})
            except Exception as exc:  # noqa: BLE001
                logger.warning("Perception→Memory yönlendirme atlandı: %s", exc)

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' algı erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' algı girişi (perceive) için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    @staticmethod
    def _clamp(x: float) -> float:
        return round(max(0.0, min(1.0, float(x))), 4)

    @staticmethod
    def _clamp_signed(x: float) -> float:
        return round(max(-1.0, min(1.0, float(x))), 4)

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
