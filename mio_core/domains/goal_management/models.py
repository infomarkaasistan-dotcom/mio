"""MIO Core · Goal Management Domain — hatalar, config (production-grade), LLM-BAĞIMSIZ.

E2 GoalManager'ı (uzun-vadeli hedef → milestone → görev hiyerarşisi + ilerleme + E1 senkron) governance
kabuğuyla SARAR. Çekirdek hedef modelleri (LongTermGoal/Milestone/GoalTask) yeniden kullanılır; bu modül
yalnız hata hiyerarşisi ve yetki/geçerlilik kurallarını ekler. Aynı store paylaşılır — tek doğruluk kaynağı."""

from __future__ import annotations

from dataclasses import dataclass, field

# Çekirdek hedef yapıları yeniden kullanılır (kopya yok).
from mio_core.executive.goals import GoalTask, LongTermGoal, Milestone

__all__ = [
    "LongTermGoal", "Milestone", "GoalTask", "GoalConfig", "TASK_RESULT_STATUSES",
    "GoalError", "ValidationError", "UnauthorizedError", "NotFoundError",
]

# Görev sonucu için kabul edilen statüler (record_result)
TASK_RESULT_STATUSES = ("completed", "failed", "running", "activated", "pending")


class GoalError(Exception):
    """Goal Management Domain temel hatası."""


class ValidationError(GoalError):
    pass


class UnauthorizedError(GoalError):
    pass


class NotFoundError(GoalError):
    pass


@dataclass
class GoalConfig:
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Planning", "Goal", "Reasoning", "Learning"})
    writer_actors: set = field(default_factory=lambda: {"owner", "Executive", "Planning", "Goal"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors
