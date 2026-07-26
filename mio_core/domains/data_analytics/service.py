"""MIO Core · Data Analytics Domain Service (production-grade), LLM-BAĞIMSIZ, deterministik.

Dataset registry + deterministik istatistik/aggregate/KPI + trend/anomali (stdlib). Uydurma yok — yalnız
verilen veriden. LLM ancak yorum/narrative için danışman olabilir; hesaplar çekirdektedir. authz · validation ·
events · observability · errors."""

from __future__ import annotations

import logging
from typing import Any, Optional

from . import analyzer
from .contract import CONTRACT_VERSION, DataEvents, data_contract
from .models import (
    AggOp,
    DataConfig,
    Dataset,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .repository import DataRepository

logger = logging.getLogger("mio.domain.data_analytics")


class DataAnalyticsDomain:
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, repository: DataRepository, *, bus=None,
                 config: Optional[DataConfig] = None) -> None:
        self._repo = repository
        self._bus = bus
        self._cfg = config or DataConfig()
        self._metrics = {"datasets": 0, "aggregations": 0, "kpis": 0, "anomaly_runs": 0}

    # ------------------------------------------------------------------ #
    def register_dataset(self, actor: str, name: str, rows: list[dict]) -> dict[str, Any]:
        self._authorize_writer(actor)
        name = self._require(name, "dataset adı")
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValidationError("rows: dict listesi olmalı")
        if len(rows) > self._cfg.max_rows:
            raise ValidationError(f"satır sınırı aşıldı ({self._cfg.max_rows})")
        ds = Dataset(name=name, rows=rows)
        self._repo.put(ds)
        self._metrics["datasets"] += 1
        self._emit(DataEvents.DATASET_REGISTERED, {"actor": actor, "id": ds.id, "rows": len(rows)})
        return ds.to_dict()

    def describe(self, actor: str, dataset_id: str) -> dict[str, Any]:
        self._authorize(actor)
        return analyzer.describe(self._require_ds(dataset_id).rows)

    def aggregate(self, actor: str, dataset_id: str, column: str, op: str) -> dict[str, Any]:
        self._authorize(actor)
        column = self._require(column, "sütun")
        if op not in AggOp.ALL:
            raise ValidationError(f"Geçersiz aggregate: {op} (izinli: {sorted(AggOp.ALL)})")
        ds = self._require_ds(dataset_id)
        if column not in ds.columns:
            raise ValidationError(f"Sütun yok: {column}")
        result = analyzer.aggregate(ds.rows, column, op)
        self._metrics["aggregations"] += 1
        self._emit(DataEvents.AGGREGATED, {"dataset": dataset_id, "column": column, "op": op})
        return result

    def kpi(self, actor: str, dataset_id: str, name: str, column: str, op: str) -> dict[str, Any]:
        """Adlandırılmış KPI = bir sütun üzerinde deterministik aggregate."""
        result = self.aggregate(actor, dataset_id, column, op)
        self._metrics["kpis"] += 1
        self._emit(DataEvents.KPI_COMPUTED, {"kpi": name, "value": result.get("value")})
        return {"kpi": self._require(name, "KPI adı"), **result}

    def trend(self, actor: str, series: list) -> dict[str, Any]:
        self._authorize(actor)
        if not isinstance(series, list):
            raise ValidationError("series liste olmalı")
        return analyzer.trend(series)

    def anomalies(self, actor: str, series: list, *, k: Optional[float] = None) -> dict[str, Any]:
        self._authorize(actor)
        if not isinstance(series, list):
            raise ValidationError("series liste olmalı")
        result = analyzer.anomalies(series, k=self._cfg.anomaly_k if k is None else float(k))
        self._metrics["anomaly_runs"] += 1
        if result["anomalies"]:
            self._emit(DataEvents.ANOMALY_FOUND, {"count": len(result["anomalies"])})
        return result

    def list_datasets(self, actor: str) -> list[dict[str, Any]]:
        self._authorize(actor)
        return [d.to_dict() for d in self._repo.list()]

    # ------------------------------------------------------------------ #
    def stats(self) -> dict[str, Any]:
        return {"datasets": self._repo.count(), **self._metrics,
                "contract_version": self.CONTRACT_VERSION}

    def contract(self) -> dict[str, Any]:
        return data_contract()

    # ------------------------------------------------------------------ #
    def _require_ds(self, dataset_id: str) -> Dataset:
        ds = self._repo.get(dataset_id)
        if ds is None:
            raise NotFoundError(f"Dataset bulunamadı: {dataset_id}")
        return ds

    def _authorize(self, actor: str) -> None:
        if not self._cfg.is_authorized(actor):
            raise UnauthorizedError(f"'{actor}' veri analitiği erişimi için yetkili değil")

    def _authorize_writer(self, actor: str) -> None:
        if not self._cfg.is_writer(actor):
            raise UnauthorizedError(f"'{actor}' dataset yazımı için yetkili değil")

    @staticmethod
    def _require(value: str, label: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValidationError(f"{label} boş olamaz")
        return v

    def _emit(self, event_type: str, data: dict) -> None:
        if self._bus is not None:
            self._bus.publish(event_type, data)
