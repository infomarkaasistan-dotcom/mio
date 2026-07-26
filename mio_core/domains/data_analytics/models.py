"""MIO Core · Data Analytics Domain — modeller, config (production-grade), LLM-BAĞIMSIZ.

Deterministik tablo analitiği (stdlib): dataset registry + istatistik + KPI + trend/anomali. Uydurma yok;
yalnız verilen veriden hesaplanır. Ağır kütüphane (pandas) YOK — çekirdek stdlib-only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AggOp:
    SUM = "sum"
    MEAN = "mean"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    DISTINCT = "distinct"
    MEDIAN = "median"
    ALL = {SUM, MEAN, MIN, MAX, COUNT, DISTINCT, MEDIAN}


class DataError(Exception):
    """Data Analytics Domain temel hatası."""


class ValidationError(DataError):
    pass


class UnauthorizedError(DataError):
    pass


class NotFoundError(DataError):
    pass


@dataclass
class Dataset:
    name: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(default_factory=_now)

    @property
    def columns(self) -> list[str]:
        cols: list[str] = []
        for r in self.rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        return cols

    def to_dict(self, *, include_rows: bool = False) -> dict[str, Any]:
        d = {"id": self.id, "name": self.name, "row_count": len(self.rows), "columns": self.columns,
             "created_at": self.created_at}
        if include_rows:
            d["rows"] = self.rows
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Dataset":
        return cls(name=d["name"], rows=list(d.get("rows") or []), id=d.get("id") or uuid4().hex[:12],
                   created_at=d.get("created_at") or _now())


@dataclass
class DataConfig:
    anomaly_k: float = 2.0             # mean ± k*std dışı → anomali
    max_rows: int = 100000
    authorized_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Finance", "Marketing", "Sales", "Research",
        "Planning", "Reasoning", "Business"})
    writer_actors: set = field(default_factory=lambda: {
        "owner", "Executive", "Operations", "Finance", "Research"})

    def is_authorized(self, actor: str) -> bool:
        return actor == "owner" or actor in self.authorized_actors

    def is_writer(self, actor: str) -> bool:
        return actor == "owner" or actor in self.writer_actors


__all__ = [
    "AggOp", "Dataset", "DataConfig",
    "DataError", "ValidationError", "UnauthorizedError", "NotFoundError",
]
