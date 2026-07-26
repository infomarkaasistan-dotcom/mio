"""MIO Core · Data Analytics · Analizör — DETERMİNİSTİK, stdlib-only (statistics), LLM-BAĞIMSIZ.

Sütun istatistiği + aggregate + trend + anomali. Aynı veri → aynı sonuç. Uydurma yok (yalnız veriden)."""

from __future__ import annotations

import statistics
from typing import Any

from .models import AggOp


def _numeric(values: list[Any]) -> list[float]:
    out = []
    for v in values:
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out.append(float(v))
        elif isinstance(v, str):
            try:
                out.append(float(v.replace(",", ".").strip()))
            except ValueError:
                pass
    return out


def _column(rows: list[dict], column: str) -> list[Any]:
    return [r[column] for r in rows if column in r and r[column] is not None]


def aggregate(rows: list[dict], column: str, op: str) -> dict[str, Any]:
    """Bir sütuna deterministik aggregate uygular."""
    vals = _column(rows, column)
    if op == AggOp.COUNT:
        return {"column": column, "op": op, "value": len(vals)}
    if op == AggOp.DISTINCT:
        return {"column": column, "op": op, "value": len({str(v) for v in vals})}
    nums = _numeric(vals)
    if not nums:
        return {"column": column, "op": op, "value": None, "note": "sayısal değer yok"}
    fn = {AggOp.SUM: sum, AggOp.MIN: min, AggOp.MAX: max,
          AggOp.MEAN: statistics.fmean, AggOp.MEDIAN: statistics.median}[op]
    return {"column": column, "op": op, "value": round(fn(nums), 6), "n": len(nums)}


def describe(rows: list[dict]) -> dict[str, Any]:
    """Her sütun için tip + temel istatistik (deterministik)."""
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    out = {}
    for c in cols:
        vals = _column(rows, c)
        nums = _numeric(vals)
        is_numeric = bool(vals) and len(nums) == len(vals)
        info: dict[str, Any] = {"count": len(vals), "distinct": len({str(v) for v in vals}),
                                "type": "numeric" if is_numeric else "text"}
        if nums:
            info.update({"min": round(min(nums), 6), "max": round(max(nums), 6),
                         "mean": round(statistics.fmean(nums), 6), "sum": round(sum(nums), 6)})
        out[c] = info
    return {"rows": len(rows), "columns": out}


def trend(series: list[float]) -> dict[str, Any]:
    """Deterministik trend: yön (up/down/flat), ilk→son değişim%, kaba eğim işareti."""
    nums = _numeric(series)
    if len(nums) < 2:
        return {"direction": "flat", "change_pct": 0.0, "n": len(nums), "note": "yetersiz veri"}
    first, last = nums[0], nums[-1]
    change = last - first
    change_pct = round((change / abs(first) * 100), 3) if first != 0 else None
    direction = "up" if change > 0 else "down" if change < 0 else "flat"
    return {"direction": direction, "change_pct": change_pct, "first": first, "last": last, "n": len(nums)}


def anomalies(series: list[float], *, k: float = 2.0) -> dict[str, Any]:
    """mean ± k*std dışındaki değerler (deterministik). std için >=2 değer gerekir."""
    nums = _numeric(series)
    if len(nums) < 2:
        return {"anomalies": [], "mean": None, "std": None, "n": len(nums)}
    mean = statistics.fmean(nums)
    std = statistics.pstdev(nums)
    lo, hi = mean - k * std, mean + k * std
    found = [{"index": i, "value": v} for i, v in enumerate(nums) if v < lo or v > hi]
    return {"anomalies": found, "mean": round(mean, 6), "std": round(std, 6),
            "bounds": [round(lo, 6), round(hi, 6)], "n": len(nums)}


__all__ = ["aggregate", "describe", "trend", "anomalies"]
