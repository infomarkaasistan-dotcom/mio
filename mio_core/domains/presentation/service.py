"""MIO Core · Presentation Domain Service (production-grade), LLM-BAĞIMSIZ, DETERMİNİSTİK.

Sunum mantığı: senaryo/akış/zaman/slayt/soru-cevap. **Domain ConnectorManager'ı/connector'ı ASLA çağırmaz** —
yalnız **CapabilityIntent** (soyut niyet) üretir. Niyetin yürütülmesine EXECUTIVE karar verir (ConnectorManager
yalnız Executive'te). Yüksek-risk niyet (yayın/gizlilik) onay ister (Madde 24). LLM yalnız içerik üretebilir
(danışman); akış/zaman/slayt DETERMİNİSTİK. authz · validation · events · observability · errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contract import CONTRACT_VERSION, PresentationEvents, presentation_contract
from .models import (
    CapabilityIntent,
    HIGH_RISK_INTENTS,
    INTENT_ALIASES,
    NotFoundError,
    Pace,
    PresentationConfig,
    ScriptKind,
    Script,
    Segment,
    SegmentKind,
    Session,
    SessionStatus,
    Slide,
    UnauthorizedError,
    ValidationError,
)
from .repository import PresentationRepository

logger = logging.getLogger("mio.domain.presentation")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PresentationDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: PresentationRepository, *, bus=None,
                 config: Optional[PresentationConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or PresentationConfig()
        self._metrics = {"scripts": 0, "sessions": 0, "intents_planned": 0, "high_risk_intents": 0}

    # -- senaryo / içerik (deterministik sunum mantığı) ----------------- #
    def create_script(self, actor: str, title: str, *, kind: str = ScriptKind.SPEECH, goal: str = "",
                      pace: str = Pace.NORMAL, segments: Optional[list] = None,
                      slides: Optional[list] = None) -> dict[str, Any]:
        self._authorize_writer(actor)
        title = self._require(title, "başlık")
        if kind not in ScriptKind.ALL:
            raise ValidationError(f"Geçersiz sunum türü: {kind}")
        if pace not in Pace.ALL:
            raise ValidationError(f"Geçersiz konuşma hızı: {pace}")
        segs = [self._to_segment(s) for s in (segments or [])]
        sls = [Slide.from_dict(s) if isinstance(s, dict) else s for s in (slides or [])]
        script = Script(title=title, kind=kind, goal=goal, pace=pace, segments=segs, slides=sls)
        self._repo.put_script(script)
        self._metrics["scripts"] += 1
        self._emit(PresentationEvents.SCRIPT_CREATED, {"actor": actor, "id": script.id, "kind": kind})
        return script.to_dict()

    def outline_to_script(self, actor: str, title: str, outline: list, *, kind: str = ScriptKind.SLIDES,
                          goal: str = "", pace: str = Pace.NORMAL) -> dict[str, Any]:
        """Deterministik: outline (madde listesi) → intro + her madde bir BODY segment + outro. LLM YOK."""
        self._authorize_writer(actor)
        title = self._require(title, "başlık")
        if not isinstance(outline, list) or not outline:
            raise ValidationError("outline boş olamaz (madde listesi gerekli)")
        segs = [Segment(title="Giriş", content=f"{title} — {goal}".strip(" —"), kind=SegmentKind.INTRO)]
        for i, item in enumerate(outline, 1):
            text = item if isinstance(item, str) else str(item)
            segs.append(Segment(title=f"Bölüm {i}", content=text, kind=SegmentKind.BODY))
        segs.append(Segment(title="Kapanış", content="Teşekkürler. Sorularınızı alabilirim.",
                            kind=SegmentKind.OUTRO))
        slides = [Slide(index=i, title=(o if isinstance(o, str) else str(o))[:60]) for i, o in enumerate(outline)]
        return self.create_script(actor, title, kind=kind, goal=goal, pace=pace,
                                  segments=[s.to_dict() for s in segs], slides=[s.to_dict() for s in slides])

    def add_segment(self, actor: str, script_id: str, *, title: str, content: str = "",
                    kind: str = SegmentKind.BODY, voice: str = "", position: Optional[int] = None) -> dict[str, Any]:
        self._authorize_writer(actor)
        script = self._require_script(script_id)
        if kind not in SegmentKind.ALL:
            raise ValidationError(f"Geçersiz bölüm türü: {kind}")
        seg = Segment(title=self._require(title, "bölüm başlığı"), content=content, kind=kind, voice=voice)
        if position is None or position >= len(script.segments):
            script.segments.append(seg)
        else:
            script.segments.insert(max(0, position), seg)
        script.updated_at = _now()
        self._repo.put_script(script)
        self._emit(PresentationEvents.SCRIPT_UPDATED, {"id": script_id, "segments": len(script.segments)})
        return script.to_dict()

    def add_slides(self, actor: str, script_id: str, slides: list) -> dict[str, Any]:
        self._authorize_writer(actor)
        script = self._require_script(script_id)
        base = len(script.slides)
        for i, sl in enumerate(slides):
            if isinstance(sl, dict):
                script.slides.append(Slide(index=sl.get("index", base + i), title=sl.get("title", ""),
                                           notes=sl.get("notes", "")))
            else:
                script.slides.append(Slide(index=base + i, title=str(sl)))
        script.updated_at = _now()
        self._repo.put_script(script)
        return script.to_dict()

    # -- NİYET üretimi (yürütme YOK — Executive yürütür) ---------------- #
    def intent(self, actor: str, target: str, *, request: Optional[dict] = None) -> dict[str, Any]:
        """Tek soyut hedefi ('konuş'/'yayınla'/'sun'/'altyazı') bir CapabilityIntent'e çevirir. Yürütmez."""
        self._authorize(actor)
        capability = INTENT_ALIASES.get(target, target)   # alias ya da doğrudan capability adı
        ci = self._make_intent(capability, request or {}, label=target)
        return ci.to_dict()

    def plan_delivery(self, actor: str, script_id: str) -> dict[str, Any]:
        """Script'i DETERMİNİSTİK bir niyet (CapabilityIntent) dizisine çevirir. Yürütme YOK — Executive'e sunar."""
        self._authorize(actor)
        script = self._require_script(script_id)
        intents: list[CapabilityIntent] = []

        # Canlı türler: yayını başlat (yüksek-risk → onay)
        if script.kind in (ScriptKind.LIVESTREAM, ScriptKind.WEBINAR, ScriptKind.MEETING):
            intents.append(self._make_intent("stream.start", {"title": script.title, "kind": script.kind},
                                             label="Yayını başlat"))
        # Her bölümü seslendir
        for seg in script.segments:
            intents.append(self._make_intent("speech.synthesize",
                           {"text": seg.content, "voice": seg.voice, "pace": script.pace},
                           label=f"Seslendir: {seg.title}"))
        # Slayt akışı (slayt varsa)
        for sl in script.slides[1:]:
            intents.append(self._make_intent("slide.next", {"index": sl.index}, label=f"Slayt {sl.index}"))
        # Türe özgü kapanış niyeti
        if script.kind == ScriptKind.PODCAST:
            intents.append(self._make_intent("podcast.render", {"script_id": script.id}, label="Podcast render"))
        elif script.kind == ScriptKind.VIDEO:
            intents.append(self._make_intent("video.render", {"script_id": script.id}, label="Video render"))
        if script.kind in (ScriptKind.LIVESTREAM, ScriptKind.WEBINAR, ScriptKind.MEETING):
            intents.append(self._make_intent("stream.stop", {}, label="Yayını durdur"))

        self._metrics["intents_planned"] += len(intents)
        self._metrics["high_risk_intents"] += sum(1 for i in intents if i.requires_approval)
        self._emit(PresentationEvents.DELIVERY_PLANNED, {"script_id": script_id, "intents": len(intents),
                   "high_risk": sum(1 for i in intents if i.requires_approval)})
        return {"script_id": script_id, "kind": script.kind, "duration_sec": script.duration_sec(),
                "intents": [i.to_dict() for i in intents]}

    # -- oturum (deterministik durum makinesi; slayt niyeti üretir) ----- #
    def start_session(self, actor: str, script_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        self._require_script(script_id)
        session = Session(script_id=script_id, status=SessionStatus.PLANNED)
        self._repo.put_session(session)
        self._metrics["sessions"] += 1
        self._emit(PresentationEvents.SESSION_STARTED, {"id": session.id, "script_id": script_id})
        return session.to_dict()

    def advance_slide(self, actor: str, session_id: str, *, direction: str = "next") -> dict[str, Any]:
        """Slayt imlecini deterministik ilerletir ve slide.next/previous NİYETİ üretir (yürütmez)."""
        self._authorize_writer(actor)
        session = self._require_session(session_id)
        script = self._require_script(session.script_id)
        n = len(script.slides)
        if direction == "next":
            session.slide_cursor = min(n - 1, session.slide_cursor + 1) if n else 0
            cap = "slide.next"
        else:
            session.slide_cursor = max(0, session.slide_cursor - 1)
            cap = "slide.previous"
        session.updated_at = _now()
        self._repo.put_session(session)
        self._emit(PresentationEvents.SLIDE_CHANGED, {"id": session_id, "cursor": session.slide_cursor})
        return {"session": session.to_dict(),
                "intent": self._make_intent(cap, {"index": session.slide_cursor}, label="Slayt geçişi").to_dict()}

    def end_session(self, actor: str, session_id: str) -> dict[str, Any]:
        self._authorize_writer(actor)
        session = self._require_session(session_id)
        session.status = SessionStatus.ENDED
        session.updated_at = _now()
        self._repo.put_session(session)
        self._emit(PresentationEvents.SESSION_ENDED, {"id": session_id})
        return session.to_dict()

    # -- sorgular -------------------------------------------------------- #
    def get_script(self, actor: str, script_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_script(script_id).to_dict()

    def list_scripts(self, actor: str, *, kind: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        if kind is not None and kind not in ScriptKind.ALL:
            raise ValidationError(f"Geçersiz sunum türü: {kind}")
        return [s.to_dict() for s in self._repo.all_scripts(kind=kind)]

    def get_session(self, actor: str, session_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return self._require_session(session_id).to_dict()

    def list_sessions(self, actor: str, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [s.to_dict() for s in self._repo.all_sessions(status=status)]

    def stats(self) -> dict[str, Any]:
        return {"scripts": self._repo.script_count(), "sessions": self._repo.session_count(),
                **self._metrics, "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return presentation_contract()

    # ------------------------------------------------------------------ #
    def _make_intent(self, capability: str, request: dict, *, label: str = "") -> CapabilityIntent:
        capability = self._require(capability, "capability")
        return CapabilityIntent(capability=capability, request=dict(request or {}), label=label,
                                requires_approval=capability in HIGH_RISK_INTENTS)

    @staticmethod
    def _to_segment(s) -> Segment:
        return Segment.from_dict(s) if isinstance(s, dict) else s

    def _require_script(self, script_id: str) -> Script:
        s = self._repo.get_script(script_id)
        if s is None:
            raise NotFoundError(f"Script bulunamadı: {script_id}")
        return s

    def _require_session(self, session_id: str) -> Session:
        s = self._repo.get_session(session_id)
        if s is None:
            raise NotFoundError(f"Oturum bulunamadı: {session_id}")
        return s

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' sunum erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' sunum yazma için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
