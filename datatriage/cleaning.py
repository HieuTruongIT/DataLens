"""Ordered cleaning on a deep copy. Failed plans return no partially changed data."""
import numpy as np
import pandas as pd
from .models import Action, CleaningResult
from .profiling import numeric_values, outlier_mask
from .detectors import date_values
from .validation import validate_frame

ACTION_INFO = {
    "remove_duplicates": ("Remove exact duplicate rows", "LOW", "Keep the first occurrence; order matters after other actions."),
    "trim": ("Trim whitespace", "LOW", "Trim only leading/trailing whitespace in text cells."),
    "blank_to_null": ("Blank strings → missing", "LOW", "Replace empty or whitespace-only text with missing."),
    "remove_empty_rows": ("Remove completely empty rows", "MEDIUM", "Only rows whose values are all missing are removed."),
    "remove_empty_columns": ("Remove completely empty columns", "MEDIUM", "Only columns whose values are all missing are removed."),
    "drop_column": ("Drop selected column", "HIGH", "Remove all values in this column."),
    "fill_median": ("Fill missing with median", "MEDIUM", "Use finite numeric values; reject mixed non-numeric data."),
    "fill_mean": ("Fill missing with mean", "MEDIUM", "Use finite numeric values; reject mixed non-numeric data."),
    "fill_mode": ("Fill missing with mode", "MEDIUM", "Use the most common value; ties use first appearance."),
    "fill_custom": ("Fill missing with custom text", "MEDIUM", "Insert the exact supplied text into missing cells."),
    "to_numeric": ("Convert to numeric", "HIGH", "Invalid values become missing; identifiers can lose leading zeros."),
    "to_datetime": ("Convert to datetime", "HIGH", "Use the explicit format; invalid values become missing."),
    "lowercase": ("Normalize text to lowercase", "MEDIUM", "Changes capitalization; can merge distinct categories."),
    "remove_outliers": ("Remove outlier rows", "HIGH", "Remove complete rows outside IQR bounds in the selected column."),
}
GLOBAL_ACTIONS = {"remove_duplicates", "remove_empty_rows", "remove_empty_columns"}


def changed_cells(before: pd.DataFrame, after: pd.DataFrame) -> int:
    rows = before.index.intersection(after.index)
    cols = before.columns.intersection(after.columns)
    left, right = before.loc[rows, cols], after.loc[rows, cols]
    same = left.eq(right).fillna(False) | (left.isna() & right.isna())
    return int((~same).sum().sum())


def clean(df: pd.DataFrame, actions: list[Action]) -> CleaningResult:
    validate_frame(df)
    original = df.copy(deep=True).reset_index(drop=True)
    result = original.copy(deep=True)
    log = []
    for action in actions:
        if action.kind not in ACTION_INFO:
            raise ValueError("Unknown cleaning action.")
        if action.kind not in GLOBAL_ACTIONS and action.column not in result:
            raise ValueError(f"Action refers to a missing or previously removed column: {action.column}")
        before = result.copy(deep=True)
        col, kind = action.column, action.kind
        if kind == "remove_duplicates":
            result = result.drop_duplicates()
        elif kind == "remove_empty_rows":
            result = result.dropna(how="all")
        elif kind == "remove_empty_columns":
            result = result.dropna(axis=1, how="all")
        elif kind == "drop_column":
            result = result.drop(columns=[col])
        elif kind in {"trim", "blank_to_null", "lowercase"}:
            def transform(value):
                if not isinstance(value, str):
                    return value
                if kind == "trim":
                    return value.strip()
                if kind == "lowercase":
                    return value.lower()
                return pd.NA if not value.strip() else value
            result[col] = result[col].map(transform)
        elif kind in {"fill_median", "fill_mean"}:
            nums = numeric_values(result[col])
            if (result[col].notna() & nums.isna()).any():
                raise ValueError("Numeric filling requires every existing value to parse as a number.")
            finite = nums[np.isfinite(nums)]
            if finite.empty:
                raise ValueError("No finite numeric values are available for filling.")
            replacement = float(finite.median() if kind == "fill_median" else finite.mean())
            result[col] = result[col].astype(object).where(result[col].notna(), replacement)
        elif kind in {"fill_mode", "fill_custom"}:
            if kind == "fill_mode":
                values = result[col].dropna()
                if values.empty:
                    raise ValueError("No non-missing value is available for mode filling.")
                counts = values.value_counts(sort=False)
                candidates = counts[counts == counts.max()].index
                replacement = values[values.isin(candidates)].iloc[0]
            else:
                if not isinstance(action.value, str) or not action.value.strip():
                    raise ValueError("Enter a non-blank custom replacement value.")
                replacement = action.value
            result[col] = result[col].astype(object).where(result[col].notna(), replacement)
        elif kind == "to_numeric":
            result[col] = numeric_values(result[col])
        elif kind == "to_datetime":
            if not isinstance(action.value, str) or not action.value:
                raise ValueError("Select an explicit date format.")
            result[col] = date_values(result[col], action.value)
        elif kind == "remove_outliers":
            multiplier = float(action.value if action.value is not None else 1.5)
            if not np.isfinite(multiplier) or not .5 <= multiplier <= 5:
                raise ValueError("IQR multiplier must be between 0.5 and 5.")
            nums = numeric_values(result[col])
            if (result[col].notna() & nums.isna()).any():
                raise ValueError("Outlier removal requires numeric data.")
            result = result.loc[~outlier_mask(result[col], multiplier)].copy()
        removed_rows = len(before) - len(result)
        removed_columns = len(before.columns) - len(result.columns)
        modified = changed_cells(before, result)
        log.append({"action": kind, "column": col, "parameter": action.value,
                    "risk": ACTION_INFO[kind][1], "rows_removed": removed_rows,
                    "columns_removed": removed_columns, "cells_modified": modified,
                    "new_missing_cells": int((before.loc[result.index, result.columns].notna() & result.isna()).sum().sum())})
    return CleaningResult(result, log, len(original) - len(result),
                          len(original.columns) - len(result.columns), changed_cells(original, result))
