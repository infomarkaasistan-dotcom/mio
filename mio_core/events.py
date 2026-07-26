"""MIO Core · Event Bus (Öncelik 12 temeli) — event-driven altyapı, LLM-BAĞIMSIZ, stdlib-only.

Tüm servisler event publish eder; Dashboard (ileride) yalnız subscribe eder → UI yazılınca backend değişmez.
Hafif, senkron, deterministik in-process pub/sub. Çekirdek cognition'a dokunmaz (gövde bileşeni)."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from mio_core.executive.models import now_iso

logger = logging.getLogger("mio.events")

__all__ = ["Event", "Ev", "EventBus"]

Event = dict  # {"type": str, "data": dict, "at": iso}


class Ev:
    """Event tipleri kataloğu."""
    MCP_DISCOVERED = "mcp.discovered"
    MCP_HEALTH = "mcp.health"
    CAPABILITY_ADDED = "capability.added"
    CAPABILITY_REMOVED = "capability.removed"
    TOOL_CALL = "tool.call"
    TOOL_BLOCKED = "tool.blocked"
    SANDBOX_STAGE = "sandbox.stage"
    SANDBOX_RESULT = "sandbox.result"
    VERSION_UPDATE = "version.update"
    INSTALL = "install"
    RECOMMENDATION = "recommendation"
    DIAGNOSTIC = "diagnostic"
    ANALYTICS = "analytics"
    POLICY_PROFILE = "policy.profile"
    EXECUTIVE_REPORT = "executive.report"


class EventBus:
    """Senkron pub/sub. subscribe(type)/subscribe_all + publish. İsteğe bağlı geçmiş kaydı."""

    def __init__(self, *, record: bool = False, history_limit: int = 1000, contracts=None,
                 on_subscriber_error: Optional[Callable[[Event, Callable, Exception], None]] = None) -> None:
        self._subs: dict[str, list[Callable[[Event], None]]] = {}
        self._all: list[Callable[[Event], None]] = []
        self._record = record
        self._history_limit = history_limit
        self._history: list[Event] = []
        self._contracts = contracts          # opsiyonel EventContracts → publish'e sürüm iliştirir
        # Madde 27: abone hataları ARTIK sessizce yutulmaz — görünür kılınır (sayaç + log/hook).
        self._on_error = on_subscriber_error
        self._dropped = 0
        self._recent_errors: list[dict[str, Any]] = []

    def set_error_handler(self, handler: Callable[[Event, Callable, Exception], None]) -> None:
        """Abone hatası dinleyicisi (geç-bağlama; runtime observability'ye bağlar)."""
        self._on_error = handler

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        self._subs.setdefault(event_type, []).append(handler)

    def subscribe_all(self, handler: Callable[[Event], None]) -> None:
        self._all.append(handler)

    def publish(self, event_type: str, data: Optional[dict] = None) -> Event:
        version = self._contracts.version(event_type) if self._contracts is not None else "1.0.0"
        ev: Event = {"type": event_type, "v": version, "data": dict(data or {}), "at": now_iso()}
        if self._record:
            self._history.append(ev)
            if len(self._history) > self._history_limit:
                self._history = self._history[-self._history_limit:]
        for handler in [*self._subs.get(event_type, []), *self._all]:
            try:
                handler(ev)
            except Exception as exc:  # noqa: BLE001 — bir abonenin hatası bus'ı durdurmaz AMA sessiz DEĞİL
                self._on_subscriber_error(ev, handler, exc)
        return ev

    def _on_subscriber_error(self, ev: Event, handler: Callable, exc: Exception) -> None:
        """Abone hatasını GÖRÜNÜR kılar (Madde 27): sayaç + son-hatalar halkası + hook/log. Bus'ı durdurmaz."""
        self._dropped += 1
        self._recent_errors.append({"type": ev.get("type"), "error": str(exc)[:200], "at": ev.get("at")})
        if len(self._recent_errors) > 50:
            self._recent_errors = self._recent_errors[-50:]
        if self._on_error is not None:
            try:
                self._on_error(ev, handler, exc)      # ör. observability sayacı
            except Exception:  # noqa: BLE001 — son çare: hata dinleyicisi bile bus'ı kıramaz
                logger.error("EventBus hata-dinleyicisi başarısız (%s)", ev.get("type"))
        else:
            logger.warning("EventBus abone hatası (%s): %s", ev.get("type"), exc)

    def subscriber_errors(self) -> dict[str, Any]:
        """Yutulmayan abone hataları — gözlemlenebilirlik (dropped sayısı + son hatalar)."""
        return {"dropped": self._dropped, "recent": list(self._recent_errors)}

    def history(self, event_type: Optional[str] = None, limit: int = 200) -> list[Event]:
        hs = self._history if event_type is None else [e for e in self._history if e["type"] == event_type]
        return hs[-limit:]

    def clear(self) -> None:
        self._history.clear()
