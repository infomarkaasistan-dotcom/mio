"""MIO Core · Presentation Domain — modeller, config (production-grade), LLM-BAĞIMSIZ, DETERMİNİSTİK.

**Bu domain SUNUM MANTIĞINI bilir; dış sistemleri (OBS/YouTube/Piper/Whisper/ElevenLabs/FFmpeg/Discord) İSİM
OLARAK BİLE bilmez.** Konuşma akışı, podcast/video senaryosu, sunum metni, meeting/webinar/lesson/demo akışı, bölüm
geçişleri, zaman akışı, slayt sıralaması, soru-cevap, konuşma akışı burada üretilir.

**KATMAN AYRIMI (değişmez):** Domain ConnectorManager'ı/connector'ı ASLA çağırmaz. Domain yalnız **niyet
(CapabilityIntent)** üretir — soyut hedef: "konuş" (speech.synthesize), "yayınla" (stream.start), "sun"
(slide.next), "altyazı" (subtitle.generate). Bu niyetleri **ne zaman/nasıl** çalıştıracağına EXECUTIVE karar verir;
ConnectorManager yalnız Executive tarafından kullanılır. Dış sistem seçimi Executive + Connector Manager
sorumluluğundadır. Yüksek-risk niyetler onay ister (Madde 24)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScriptKind:
    """Sunum türleri — tek domain altında toplanır (sesli asistan/eğitim/webinar/satış/avatar/AI influencer)."""
    SPEECH = "speech"
    PODCAST = "podcast"
    VIDEO = "video"
    MEETING = "meeting"
    WEBINAR = "webinar"
    LIVESTREAM = "livestream"
    LESSON = "lesson"
    DEMO = "demo"
    SCREEN_SHARE = "screen_share"
    SLIDES = "slides"
    AVATAR = "avatar"
    CONVERSATION = "conversation"
    ALL = {SPEECH, PODCAST, VIDEO, MEETING, WEBINAR, LIVESTREAM, LESSON, DEMO, SCREEN_SHARE,
           SLIDES, AVATAR, CONVERSATION}


class SegmentKind:
    INTRO = "intro"
    BODY = "body"
    TRANSITION = "transition"
    QA = "qa"
    OUTRO = "outro"
    ALL = {INTRO, BODY, TRANSITION, QA, OUTRO}


class Pace:
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"
    ALL = {SLOW, NORMAL, FAST}
    # deterministik: kelime/dakika (konuşma hızı → süre tahmini)
    WPM = {SLOW: 110, NORMAL: 140, FAST: 170}


class SessionStatus:
    PLANNED = "planned"
    LIVE = "live"
    PAUSED = "paused"
    ENDED = "ended"
    ALL = {PLANNED, LIVE, PAUSED, ENDED}


# Yüksek-risk capability niyetleri (yayın/gizlilik) → Executive ONAY ister (Madde 24).
# NOT: Bunlar capability İSİMLERİDİR (paylaşılan protokol/sözleşme) — domain connector katmanını import ETMEZ.
HIGH_RISK_INTENTS = frozenset({
    "stream.start", "stream.stop", "podcast.publish", "video.publish",
    "screen.share", "camera.capture", "microphone.record",
})

# Soyut hedef → capability eşlemesi (domain "konuş/yayınla/sun/altyazı" gibi soyut hedeflerle çalışır).
INTENT_ALIASES = {
    "speak": "speech.synthesize", "say": "speech.synthesize", "narrate": "speech.synthesize",
    "listen": "speech.transcribe", "transcribe": "speech.transcribe",
    "publish": "podcast.publish", "golive": "stream.start", "stream": "stream.start",
    "stop_stream": "stream.stop", "present": "slide.next", "next_slide": "slide.next",
    "prev_slide": "slide.previous", "subtitle": "subtitle.generate", "caption": "subtitle.generate",
    "translate_subtitle": "subtitle.translate", "share_screen": "screen.share", "record": "microphone.record",
}


class PresentationError(Exception):
    """Presentation Domain temel hatası."""


class ValidationError(PresentationError):
    pass


class UnauthorizedError(PresentationError):
    pass


class NotFoundError(PresentationError):
    pass


def estimate_seconds(text: str, pace: str = Pace.NORMAL) -> int:
    """Deterministik süre tahmini: kelime sayısı / (WPM/60). Konuşma hızı yönetimi (Anayasa: sunum mantığı)."""
    words = len((text or "").split())
    wpm = Pace.WPM.get(pace, Pace.WPM[Pace.NORMAL])
    return int(round(words / (wpm / 60.0))) if words else 0


@dataclass
class Segment:
    title: str
    content: str = ""
    kind: str = SegmentKind.BODY
    voice: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:8])

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "content": self.content, "kind": self.kind,
                "voice": self.voice}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Segment":
        return cls(title=d["title"], content=d.get("content", ""), kind=d.get("kind", SegmentKind.BODY),
                   voice=d.get("voice", ""), id=d.get("id") or uuid4().hex[:8])


@dataclass
class Slide:
    index: int
    title: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "title": self.title, "notes": self.notes}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Slide":
        return cls(index=int(d["index"]), title=d["title"], notes=d.get("notes", ""))


@dataclass
class Script:
    title: str
    kind: str = ScriptKind.SPEECH
    goal: str = ""
    pace: str = Pace.NORMAL
    segments: list = field(default_factory=list)     # Segment
    slides: list = field(default_factory=list)       # Slide
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def duration_sec(self) -> int:
        return sum(estimate_seconds(s.content, self.pace) for s in self.segments)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "kind": self.kind, "goal": self.goal, "pace": self.pace,
                "segments": [s.to_dict() for s in self.segments], "slides": [s.to_dict() for s in self.slides],
                "duration_sec": self.duration_sec(), "created_at": self.created_at,
                "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Script":
        return cls(title=d["title"], kind=d.get("kind", ScriptKind.SPEECH), goal=d.get("goal", ""),
                   pace=d.get("pace", Pace.NORMAL),
                   segments=[Segment.from_dict(x) for x in d.get("segments", [])],
                   slides=[Slide.from_dict(x) for x in d.get("slides", [])],
                   id=d.get("id") or uuid4().hex[:12], created_at=d.get("created_at") or _now(),
                   updated_at=d.get("updated_at") or _now())


@dataclass
class Session:
    script_id: str
    status: str = SessionStatus.PLANNED
    segment_cursor: int = 0
    slide_cursor: int = 0
    stream_ref: str = ""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "script_id": self.script_id, "status": self.status,
                "segment_cursor": self.segment_cursor, "slide_cursor": self.slide_cursor,
                "stream_ref": self.stream_ref, "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Session":
        return cls(script_id=d["script_id"], status=d.get("status", SessionStatus.PLANNED),
                   segment_cursor=int(d.get("segment_cursor", 0)), slide_cursor=int(d.get("slide_cursor", 0)),
                   stream_ref=d.get("stream_ref", ""), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now(), updated_at=d.get("updated_at") or _now())


@dataclass
class CapabilityIntent:
    """Domain'in ürettiği NİYET (yürütme DEĞİL). Executive bunu ConnectorManager ile yürütür (ya da yürütmez).

    Domain hangi connector'ın çalışacağını BİLMEZ — yalnız soyut capability + request üretir."""
    capability: str                      # ör: "speech.synthesize", "stream.start", "slide.next"
    request: dict = field(default_factory=dict)
    label: str = ""                      # insan-okur açıklama ("Intro'yu seslendir")
    requires_approval: bool = False      # yüksek-risk (yayın/gizlilik) → Executive onay ister (Madde 24)

    def to_dict(self) -> dict[str, Any]:
        return {"capability": self.capability, "request": dict(self.request), "label": self.label,
                "requires_approval": self.requires_approval}


@dataclass
class PresentationConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Communication", "Planning", "Marketing"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Communication", "Marketing"})
    # Madde 24: yüksek-risk medya (yayın/publish/ekran/kamera/mikrofon) yalnız bunlarca onaylanır
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors

    def is_approver(self, actor: str) -> bool:
        return actor == "owner" or actor in self.approver_actors


__all__ = [
    "ScriptKind", "SegmentKind", "Pace", "SessionStatus", "HIGH_RISK_INTENTS", "INTENT_ALIASES",
    "estimate_seconds", "Segment", "Slide", "Script", "Session", "CapabilityIntent", "PresentationConfig",
    "PresentationError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
