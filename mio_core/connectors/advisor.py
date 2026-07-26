"""MIO Core · Advisor — LLM danışman yüzeyi (Anayasa Madde 1: LLM DANIŞMAN, karar verici DEĞİL).

Executive `advisor.ask(prompt)` çağırır; hangi AI connector'ın (Ollama/OpenAI/Gemini/Claude) yanıtladığına
KARIŞMAZ ve asla `openai.chat()` GÖRMEZ. AI connector bağlı değilse dürüst `connector_unavailable` döner —
Executive tavsiye olmadan DETERMİNİSTİK çalışmaya devam eder (karar merci hep Executive). Danışman KARAR VERMEZ."""

from __future__ import annotations

from typing import Any, Optional

from .models import Cap
from .manager import ConnectorManager


class Advisor:
    def __init__(self, manager: ConnectorManager) -> None:
        self._m = manager

    def available(self) -> bool:
        """Bir AI danışman (ai.advise) bağlı mı?"""
        return self._m.available(Cap.AI_ADVISE)

    def ask(self, prompt: str, *, context: Optional[dict] = None,
            actor: str = "Executive") -> dict[str, Any]:
        """Danışmana sorar. Sonuç bir TAVSİYEDİR (karar değil); connector yoksa connector_unavailable (çökmez)."""
        return self._m.execute(Cap.AI_ADVISE, {"prompt": prompt, "context": dict(context or {})},
                               actor=actor)

    def embed(self, text: str, *, actor: str = "Executive") -> dict[str, Any]:
        return self._m.execute(Cap.AI_EMBED, {"text": text}, actor=actor)


__all__ = ["Advisor"]
