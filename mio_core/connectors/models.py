"""MIO Core · Capability Adapter Layer — modeller (production-grade), LLM-BAĞIMSIZ, DETERMİNİSTİK.

**Executive yalnız `execute(capability, request)` bilir**; hangi connector'ın çalışacağına KARIŞMAZ (Connector
Manager karar verir). Connector'lar dış sistemlere ADAPTER'dır; Executive'in içine kod gömülmez (Madde 15/16).
Connector bağlı değilse sistem ÇÖKMEZ → dürüst `connector_unavailable` (Madde 8). AI connector'lar DANIŞMAN'dır,
karar VERMEZ (Madde 1). System capability'leri (shell/docker/k8s/git-mutasyon) geri-alınamaz → ONAY ister
(Madde 24)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class ConnectorCategory:
    AI = "ai"                    # danışman: Ollama/OpenAI/Gemini/Claude (karar VERMEZ)
    COMMUNICATION = "communication"   # SMTP/Gmail/Slack/Discord/WhatsApp/Telegram
    PRODUCTIVITY = "productivity"     # Calendar/Outlook/Drive/OneDrive/Dropbox
    SYSTEM = "system"            # Shell/Filesystem/Docker/Kubernetes/Git/GitHub
    MEDIA = "media"              # TTS/STT/stream/podcast/video/screen/camera (Presentation Domain kullanır)
    ALL = {AI, COMMUNICATION, PRODUCTIVITY, SYSTEM, MEDIA}


class Cap:
    """İyi-bilinen capability kimlikleri (connector'lar bunları SAĞLAR; isimle değil capability ile çağrılır)."""
    # AI (danışman)
    AI_ADVISE = "ai.advise"
    AI_EMBED = "ai.embed"
    AI_VISION = "ai.vision"
    AI_TRANSCRIBE = "ai.transcribe"
    # Communication
    SEND_EMAIL = "send_email"
    SEND_MESSAGE = "send_message"
    # Productivity
    CALENDAR_CREATE = "calendar.create_event"
    CALENDAR_LIST = "calendar.list_events"
    FILES_READ = "files.read"
    FILES_WRITE = "files.write"
    FILES_LIST = "files.list"
    # System
    SHELL_EXEC = "shell.exec"
    FS_READ = "fs.read"
    FS_WRITE = "fs.write"
    DOCKER_RUN = "docker.run"
    K8S_APPLY = "k8s.apply"
    GIT_CLONE = "git.clone"
    GITHUB_PR = "github.pr"
    # Media (Presentation Domain bunları capability olarak ister; connector adapter sağlar)
    SPEECH_SYNTHESIZE = "speech.synthesize"
    SPEECH_TRANSCRIBE = "speech.transcribe"
    AUDIO_RECORD = "audio.record"
    AUDIO_PLAY = "audio.play"
    AUDIO_MIX = "audio.mix"
    AUDIO_CONVERT = "audio.convert"
    STREAM_START = "stream.start"
    STREAM_STOP = "stream.stop"
    STREAM_SEND_AUDIO = "stream.send_audio"
    STREAM_CAPTURE = "stream.capture"
    PODCAST_RENDER = "podcast.render"
    PODCAST_PUBLISH = "podcast.publish"
    VIDEO_RENDER = "video.render"
    VIDEO_ENCODE = "video.encode"
    VIDEO_PUBLISH = "video.publish"
    CAMERA_CAPTURE = "camera.capture"
    SCREEN_CAPTURE = "screen.capture"
    SCREEN_SHARE = "screen.share"
    MICROPHONE_RECORD = "microphone.record"
    SUBTITLE_GENERATE = "subtitle.generate"
    SUBTITLE_TRANSLATE = "subtitle.translate"
    SLIDE_NEXT = "slide.next"
    SLIDE_PREVIOUS = "slide.previous"
    # Conversation (canlı etkileşim — Communication connector'lar sağlar: Discord/Slack/Telegram/YouTube...)
    CONV_RECEIVE = "conversation.receive"
    CONV_REPLY = "conversation.reply"
    CONV_BROADCAST = "conversation.broadcast"
    CONV_PRIVATE_REPLY = "conversation.private_reply"
    CONV_PIN = "conversation.pin"
    CONV_DELETE = "conversation.delete"
    CONV_TIMEOUT = "conversation.timeout"
    CONV_BAN = "conversation.ban"
    CONV_REACTION = "conversation.reaction"
    NOTIFICATION_SEND = "notification.send"


# Geri-alınamaz/tehlikeli/gizlilik-riskli capability'ler → ONAY ister (Madde 24).
HIGH_RISK_CAPABILITIES = frozenset({
    # System/mutasyon
    Cap.SHELL_EXEC, Cap.FS_WRITE, Cap.FILES_WRITE, Cap.DOCKER_RUN, Cap.K8S_APPLY, Cap.GITHUB_PR,
    # Media: dış yayın / gizlilik (canlı yayın, yayınlama, ekran/kamera/mikrofon)
    Cap.STREAM_START, Cap.STREAM_STOP, Cap.PODCAST_PUBLISH, Cap.VIDEO_PUBLISH,
    Cap.SCREEN_SHARE, Cap.CAMERA_CAPTURE, Cap.MICROPHONE_RECORD,
    # Conversation: moderasyon / kitle (geri-alınamaz sosyal etki)
    Cap.CONV_DELETE, Cap.CONV_TIMEOUT, Cap.CONV_BAN, Cap.CONV_BROADCAST, Cap.CONV_PIN,
})


class Outcome:
    EXECUTED = "executed"
    CONNECTOR_UNAVAILABLE = "connector_unavailable"   # capability'yi sağlayan connector yok (dürüst)
    REQUIRES_APPROVAL = "requires_approval"           # yüksek-risk, onay bekliyor (Madde 24)
    FAILED = "failed"                                 # tüm sağlayıcılar denendi, başarısız


class ConnectorError(Exception):
    """Connector katmanı temel hatası."""


class ValidationError(ConnectorError):
    pass


class CapabilityNotSupported(ConnectorError):
    pass


@dataclass
class HealthStatus:
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "detail": self.detail}


@dataclass
class CallableConnector:
    """Bir dış sistem ADAPTER'ı: sağladığı capability'leri {capability: fn} olarak tutar (DI ile bağlanır).

    Executive bunu asla doğrudan görmez; yalnız Connector Manager çağırır. `execute` yalnız sağlanan
    capability için çalışır."""
    name: str
    category: str
    handlers: dict = field(default_factory=dict)   # capability -> Callable[[dict], Any]
    priority: int = 100                            # yüksek = tercih edilir
    health_fn: Optional[Callable[[], bool]] = None

    def __post_init__(self) -> None:
        if self.category not in ConnectorCategory.ALL:
            raise ValidationError(f"Geçersiz connector kategorisi: {self.category}")
        if not self.name or not str(self.name).strip():
            raise ValidationError("connector adı boş olamaz")
        if not self.handlers:
            raise ValidationError("connector en az bir capability sağlamalı")

    @property
    def capabilities(self) -> tuple:
        return tuple(sorted(self.handlers))

    def provides(self, capability: str) -> bool:
        return capability in self.handlers

    def health(self) -> HealthStatus:
        try:
            ok = bool(self.health_fn()) if self.health_fn is not None else True
            return HealthStatus(ok=ok, detail="" if ok else "unhealthy")
        except Exception as exc:  # noqa: BLE001 — health hatası = unhealthy (dürüst), çökmez
            return HealthStatus(ok=False, detail=str(exc)[:120])

    def execute(self, capability: str, request: dict) -> Any:
        fn = self.handlers.get(capability)
        if fn is None:
            raise CapabilityNotSupported(f"{self.name} '{capability}' sağlamıyor")
        return fn(dict(request or {}))

    def to_dict(self) -> dict[str, Any]:
        h = self.health()
        return {"name": self.name, "category": self.category, "capabilities": list(self.capabilities),
                "priority": self.priority, "health": h.to_dict()}


@dataclass
class ConnectorConfig:
    # Madde 24: yüksek-risk capability'yi yalnız bunlar onaylayabilir (bilgi amaçlı; onay caller assert'iyle)
    approver_actors: set = field(default_factory=lambda: {"owner", "Executive"})
    high_risk: frozenset = HIGH_RISK_CAPABILITIES

    def is_high_risk(self, capability: str) -> bool:
        return capability in self.high_risk


def unavailable_result(capability: str) -> dict[str, Any]:
    return {"ok": False, "status": Outcome.CONNECTOR_UNAVAILABLE, "capability": capability,
            "message": f"{capability} connector not configured"}


def requires_approval_result(capability: str) -> dict[str, Any]:
    return {"ok": False, "status": Outcome.REQUIRES_APPROVAL, "capability": capability,
            "message": f"{capability} geri-alınamaz — onay gerekli (Madde 24)"}


def executed_result(capability: str, connector: str, result: Any) -> dict[str, Any]:
    return {"ok": True, "status": Outcome.EXECUTED, "capability": capability,
            "connector": connector, "result": result}


def failed_result(capability: str, errors: list) -> dict[str, Any]:
    return {"ok": False, "status": Outcome.FAILED, "capability": capability, "errors": errors}


__all__ = [
    "ConnectorCategory", "Cap", "HIGH_RISK_CAPABILITIES", "Outcome", "HealthStatus", "CallableConnector",
    "ConnectorConfig", "ConnectorError", "ValidationError", "CapabilityNotSupported",
    "unavailable_result", "requires_approval_result", "executed_result", "failed_result",
]
