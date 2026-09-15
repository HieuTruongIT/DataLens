"""Explicit heuristics with affected row positions and human-readable reasons."""
import re
import numpy as np
import pandas as pd
from .models import Issue, Settings
from .profiling import inferred_type, numeric_values, outlier_mask
from .validation import validate_frame, validate_settings

DATE_FORMATS = {"ISO (2024-12-31)": "%Y-%m-%d", "Day first (31/12/2024)": "%d/%m/%Y", "Month first (12/31/2024)": "%m/%d/%Y"}


def date_values(series: pd.Series, date_format: str) -> pd.Series:
    # exact parsing; explicit format resolves ambiguous day/month ordering.
    return pd.to_datetime(series, format=date_format, errors="coerce", exact=True)


def detect_issues(df: pd.DataFrame, settings: Settings = Settings(), notes: list[str] | None = None) -> list[Issue]:
    validate_frame(df)
    validate_settings(df, settings)
    issues: list[Issue] = []

    def add(kind, col, severity, mask, explanation, action, unit="cells"):
        mask = np.asarray(mask, dtype=bool)
        count = int(mask.sum())
        if count:
            issues.append(Issue(kind, col, severity, count, count / len(mask) * 100 if len(mask) else 0,
                                explanation, action, tuple(int(x) for x in np.flatnonzero(mask)), unit))

    if len(df.columns):
        add("duplicate_rows", None, "MEDIUM", df.duplicated(), "Exact duplicate rows after the first occurrence.", "Review and optionally remove exact duplicate rows.", "rows")
    for col in df:
        s = df[col]
        missing = s.isna()
        if len(s):
            add("missing", col, "HIGH" if missing.mean() >= .2 else "LOW", missing, "Null cells; empty CSV fields are null, whitespace is not.", "Inspect missingness before selecting a fill operation.")
            if missing.all():
                add("empty_column", col, "MEDIUM", missing, "Every cell in this column is missing.", "Optionally remove the empty column.")
            elif missing.mean() >= settings.almost_empty:
                add("almost_empty", col, "MEDIUM", missing, f"At least {settings.almost_empty:.0%} of this column is missing.", "Review whether the column is still useful.")
            if s.nunique() == 1:
                add("constant", col, "INFO", ~missing, "All non-missing values are identical.", "Inspect; a constant can be legitimate.")
        add("whitespace", col, "LOW", s.map(lambda v: isinstance(v, str) and v != v.strip()), "Leading or trailing whitespace in text.", "Optionally trim whitespace.")
        add("blank_text", col, "LOW", s.map(lambda v: isinstance(v, str) and not v.strip()), "Empty or whitespace-only text is not yet a null value.", "Optionally convert blank strings to missing.")
        values = s.dropna()
        types = set(values.map(lambda v: type(v).__name__))
        nums = numeric_values(s) if inferred_type(s) != "datetime" else pd.Series(np.nan, index=s.index)
        numeric_mask = nums.notna()
        if len(types) > 1:
            add("mixed_types", col, "MEDIUM", ~missing, "Multiple stored Python types: " + ", ".join(sorted(types)), "Review before explicit type conversion.")
        elif numeric_mask.any() and (~numeric_mask & ~missing).any():
            add("mixed_numeric_text", col, "MEDIUM", ~numeric_mask & ~missing, "Some non-missing values parse as numbers and others do not.", "Inspect values; they may be valid identifiers or categories.")
        add("infinite", col, "HIGH", np.isinf(nums), "Positive or negative infinity cannot be used in finite summaries.", "Review the source; numeric conversion does not repair infinity.")
        if inferred_type(s) == "numeric":
            add("outlier", col, "INFO", outlier_mask(s, settings.iqr_multiplier),
                f"Outside Q1 − {settings.iqr_multiplier:g} × IQR or Q3 + {settings.iqr_multiplier:g} × IQR (finite values; at least 4). Outlier does not necessarily mean incorrect data.",
                "Inspect; optional row removal is high risk.")
        text = values[values.map(lambda v: isinstance(v, str))]
        variants: dict[str, set[str]] = {}
        for value in text.unique():
            variants.setdefault(value.strip().casefold(), set()).add(value)
        inconsistent = {value for group in variants.values() if len(group) > 1 for value in group}
        add("category_variants", col, "LOW", s.isin(inconsistent), "Values differ only in capitalization or surrounding whitespace.", "Review optional trim / capitalization normalization.")
        shapes = text.map(lambda v: "ISO" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()) else "slash" if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", v.strip()) else "")
        if shapes.ne("").any():
            if shapes[shapes.ne("")].nunique() > 1:
                add("mixed_date_formats", col, "LOW", s.isin(text[shapes.ne("")]), "Both ISO and slash-separated date-like strings are present. No date meaning is assumed.", "Set an explicit date validation format; review before conversion.")
            if not any(r.kind == "date" and r.column == col for r in settings.rules):
                add("date_like", col, "INFO", s.isin(text[shapes.ne("")]), "Date-shaped text detected; ambiguous dates require an explicit format.", "Configure a date rule in the sidebar to count invalid dates.")
        if col.startswith("Unnamed:"):
            add("index_like", col, "INFO", np.ones(len(s), dtype=bool), "Unnamed header may be an exported index; it could still be useful data.", "Inspect before explicitly dropping the column.")
    # Equal-value columns can be meaningful; flag without removing.
    fingerprints: dict[tuple, list[str]] = {}
    for col in df:
        key = (str(df[col].dtype), int(pd.util.hash_pandas_object(df[col], index=False).sum()))
        for other in fingerprints.get(key, []):
            if df[col].equals(df[other]):
                add("duplicate_column", col, "INFO", np.ones(len(df), dtype=bool), f'Values match column "{other}" exactly.', "Review whether both columns are needed.")
                break
        fingerprints.setdefault(key, []).append(col)
    for rule in settings.rules:
        s = df[rule.column]
        if rule.kind == "date":
            add("invalid_date", rule.column, "HIGH", s.notna() & date_values(s, rule.date_format).isna(), f"Non-null values fail the configured date format {rule.date_format}.", "Correct the source or explicitly convert; invalid values become missing.")
        elif rule.kind == "numeric":
            add("invalid_numeric", rule.column, "HIGH", s.notna() & numeric_values(s).isna(), "Non-null values cannot be parsed as numbers under the configured rule.", "Correct values or explicitly convert; invalid values become missing.")
        elif rule.kind == "identifier":
            add("duplicate_identifier", rule.column, "HIGH", s.notna() & s.duplicated(keep=False), "All occurrences of repeated, non-null identifiers under the configured rule.", "Review repeated identifiers; no automatic deletion.")
        elif rule.kind == "range":
            nums = numeric_values(s)
            bad = s.notna() & (nums.isna() | ~np.isfinite(nums))
            if rule.minimum is not None:
                bad |= nums < rule.minimum
            if rule.maximum is not None:
                bad |= nums > rule.maximum
            add("range_violation", rule.column, "HIGH", bad, f"Configured numeric range: {rule.minimum} to {rule.maximum}; non-numeric/infinite values also fail.", "Correct the source; no automatic clipping.")
    for note in notes or []:
        if note.startswith("Duplicate column name"):
            issues.append(Issue("duplicate_header", None, "MEDIUM", 1, 100 / max(len(df.columns), 1), note, "Import names were made unique to preserve every column.", (), "columns"))
    return issues
