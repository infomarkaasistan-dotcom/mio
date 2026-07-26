"""MIO Core · Data Analytics Domain — Public Contract (versioned)."""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0.0"


class DataEvents:
    DATASET_REGISTERED = "data.dataset_registered"
    AGGREGATED = "data.aggregated"
    KPI_COMPUTED = "data.kpi_computed"
    ANOMALY_FOUND = "data.anomaly_found"


OPERATIONS = ("register_dataset", "describe", "aggregate", "kpi", "trend", "anomalies",
              "list_datasets", "stats")


def data_contract() -> dict[str, Any]:
    return {
        "domain": "data_analytics",
        "version": CONTRACT_VERSION,
        "description": "Deterministik tablo analitiği (stdlib): dataset + istatistik + KPI + trend/anomali. "
                       "Ağır kütüphane yok; uydurma yok (yalnız veriden). LLM-bağımsız.",
        "operations": list(OPERATIONS),
        "events": [DataEvents.DATASET_REGISTERED, DataEvents.AGGREGATED, DataEvents.KPI_COMPUTED,
                   DataEvents.ANOMALY_FOUND],
        "aggregations": ["sum", "mean", "min", "max", "count", "distinct", "median"],
        "invariants": ["analitik deterministiktir (aynı veri → aynı sonuç)",
                       "yalnız verilen veriden hesaplanır (uydurma yok)",
                       "anomali = mean ± k*std dışı (deterministik eşik)"],
    }
