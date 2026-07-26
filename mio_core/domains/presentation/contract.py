"""MIO Core · Presentation Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class PresentationEvents:
    SCRIPT_CREATED = "presentation.script_created"
    SCRIPT_UPDATED = "presentation.script_updated"
    DELIVERY_PLANNED = "presentation.delivery_planned"      # niyet listesi üretildi (yürütme DEĞİL)
    SESSION_STARTED = "presentation.session_started"
    SLIDE_CHANGED = "presentation.slide_changed"
    SESSION_ENDED = "presentation.session_ended"
    APPROVAL_REQUIRED = "presentation.approval_required"     # yüksek-risk niyet (yayın/gizlilik)


OPERATIONS = ("create_script", "outline_to_script", "add_segment", "add_slides", "plan_delivery",
              "intent", "start_session", "advance_slide", "end_session", "get_script", "list_scripts",
              "get_session", "list_sessions", "stats")


def presentation_contract() -> dict[str, Any]:
    return {
        "domain": "presentation",
        "version": CONTRACT_VERSION,
        "description": "Sunum mantığı: konuşma/podcast/video/meeting/webinar/livestream/lesson/demo/slide/avatar/"
                       "conversation senaryosu + akış + zaman + slayt sıralaması + soru-cevap. Dış sistemleri "
                       "BİLMEZ; yalnız soyut capability NİYETİ (CapabilityIntent) üretir. Yürütmeye Executive "
                       "karar verir (ConnectorManager yalnız Executive'te). Yüksek-risk niyet onay ister (Madde 24).",
        "operations": list(OPERATIONS),
        "events": [PresentationEvents.SCRIPT_CREATED, PresentationEvents.SCRIPT_UPDATED,
                   PresentationEvents.DELIVERY_PLANNED, PresentationEvents.SESSION_STARTED,
                   PresentationEvents.SLIDE_CHANGED, PresentationEvents.SESSION_ENDED,
                   PresentationEvents.APPROVAL_REQUIRED],
        "script_kinds": ["speech", "podcast", "video", "meeting", "webinar", "livestream", "lesson",
                         "demo", "screen_share", "slides", "avatar", "conversation"],
        "capability_targets": ["speech.synthesize", "speech.transcribe", "podcast.render", "podcast.publish",
                               "video.render", "stream.start", "stream.stop", "stream.send_audio",
                               "screen.share", "slide.next", "slide.previous", "subtitle.generate"],
        "invariants": ["domain dış sistemleri (OBS/Piper/Whisper/...) İSİM olarak bile bilmez",
                       "domain ConnectorManager/connector ÇAĞIRMAZ; yalnız CapabilityIntent üretir",
                       "niyetin yürütülmesine EXECUTIVE karar verir (ConnectorManager yalnız Executive'te)",
                       "sunum mantığı (akış/zaman/slayt) DETERMİNİSTİK; LLM yalnız içerik üretir (danışman)",
                       "yüksek-risk niyet (yayın/publish/ekran/kamera/mikrofon) onay ister (Madde 24)"],
    }
