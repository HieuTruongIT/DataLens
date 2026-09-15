"""Descriptive statistics without changing source values."""
import numpy as np
import pandas as pd


def numeric_values(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def inferred_type(series: pd.Series) -> str:
    values = series.dropna()
    if values.empty:
        return "empty"
    if pd.api.types.is_bool_dtype(series) or values.map(lambda x: isinstance(x, (bool, np.bool_))).all():
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    nums = numeric_values(values)
    if nums.notna().all():
        return "numeric"
    return "text"


def overview(df: pd.DataFrame) -> dict:
    cells = int(df.size)
    return {
        "rows": len(df), "columns": len(df.columns), "cells": cells,
        "memory_bytes": int(df.memory_usage(deep=True).sum()),
        "missing_cells": int(df.isna().sum().sum()),
        "missing_percentage": float(df.isna().sum().sum() / cells * 100) if cells else 0.0,
        "duplicate_rows": int(df.duplicated().sum()) if len(df.columns) else 0,
        "types": {kind: sum(inferred_type(df[c]) == kind for c in df) for kind in ("numeric", "text", "datetime", "boolean", "empty")},
    }


def column_profile(series: pd.Series) -> dict:
    kind = inferred_type(series)
    nonnull = series.dropna()
    result = {
        "type": kind, "non_null": int(series.notna().sum()),
        "missing": int(series.isna().sum()),
        "missing_percentage": float(series.isna().mean() * 100) if len(series) else 0.0,
        "unique": int(series.nunique()),
    }
    if kind == "numeric":
        finite = numeric_values(series).replace([np.inf, -np.inf], np.nan).dropna()
        result["finite_count"] = len(finite)
        for name, value in {
            "mean": finite.mean(), "median": finite.median(), "std": finite.std(),
            "minimum": finite.min(), "maximum": finite.max(),
            "q1": finite.quantile(.25), "q3": finite.quantile(.75),
        }.items():
            result[name] = float(value) if pd.notna(value) and np.isfinite(value) else None
    elif kind == "datetime":
        result["minimum"] = nonnull.min().isoformat() if len(nonnull) else None
        result["maximum"] = nonnull.max().isoformat() if len(nonnull) else None
    else:
        lengths = nonnull.map(lambda x: len(str(x)))
        result.update(minimum_length=int(lengths.min()) if len(lengths) else None,
                      maximum_length=int(lengths.max()) if len(lengths) else None,
                      average_length=float(lengths.mean()) if len(lengths) else None,
                      common_values=[{"value": str(v), "count": int(n)} for v, n in nonnull.astype(str).value_counts().head(8).items()])
    return result


def outlier_mask(series: pd.Series, multiplier: float = 1.5) -> pd.Series:
    values = numeric_values(series).replace([np.inf, -np.inf], np.nan)
    finite = values.dropna()
    if len(finite) < 4:
        return pd.Series(False, index=series.index)
    q1, q3 = finite.quantile([.25, .75])
    return (values < q1 - multiplier * (q3 - q1)) | (values > q3 + multiplier * (q3 - q1))
