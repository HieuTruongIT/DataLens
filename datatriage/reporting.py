"""Strict JSON reports and formula-safe spreadsheet exports."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
from io import BytesIO
import json
from itertools import chain
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from .models import Settings, CleaningResult
from .profiling import overview
from .detectors import detect_issues
from .scoring import quality_score


def analyze(df: pd.DataFrame, settings: Settings, notes: list[str] | None = None) -> dict:
    issues = detect_issues(df, settings, notes)
    return {"overview": overview(df), "issues": issues, "score": quality_score(df, issues)}


def report_dict(original: pd.DataFrame, result: CleaningResult | None, settings: Settings, notes: list[str] | None = None) -> dict:
    def summary(df, active_settings):
        analysis = analyze(df, active_settings, notes)
        serialized = []
        for issue in analysis["issues"]:
            item = asdict(issue)
            item["rows"] = list(issue.rows[:100])
            item["rows_truncated"] = len(issue.rows) > 100
            serialized.append(item)
        return {"overview": analysis["overview"], "score": analysis["score"], "issues": serialized}
    after_settings = replace(settings, rules=tuple(r for r in settings.rules if result is None or r.column in result.frame))
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": "DataTriage", "source_notes": notes or [],
        "settings": asdict(settings), "row_positions": "Zero-based positions within the corresponding before/after dataset; first 100 per issue.",
        "before": summary(original, settings),
        "after": summary(result.frame.reset_index(drop=True), after_settings) if result is not None else None,
        "actions_applied": result.log if result is not None else [],
        "changes": {"rows_removed": result.rows_removed, "columns_removed": result.columns_removed,
                    "cells_modified_surviving": result.cells_modified} if result is not None else None,
        "limitations": "Heuristic score, not certification. Outliers need judgment. Reports contain column names and row positions, not row values.",
    }


def json_bytes(report: dict) -> bytes:
    def encode(value):
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(f"Cannot serialize {type(value).__name__}")
    return json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False, default=encode).encode("utf-8")


def _safe_text(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_bytes(df: pd.DataFrame, spreadsheet_safe: bool = True) -> bytes:
    export = df.copy(deep=True)
    if spreadsheet_safe:
        export = export.map(_safe_text)
        export.columns = [_safe_text(c) for c in export.columns]
    return export.to_csv(index=False).encode("utf-8-sig")


def xlsx_bytes(df: pd.DataFrame) -> bytes:
    for value in chain(df.columns, df.to_numpy().flat):
        if isinstance(value, str) and (len(value) > 32767 or ILLEGAL_CHARACTERS_RE.search(value)):
            raise ValueError("Excel cannot store control characters or text longer than 32,767 characters. Use CSV instead.")
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Cleaned data")
    from openpyxl.cell import WriteOnlyCell
    def cell(value):
        if pd.isna(value):
            return None
        if isinstance(value, (np.integer, np.floating)):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            value = str(value)
        if isinstance(value, pd.Timestamp):
            value = value.isoformat()
        if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 999999999999999:
            value = str(value)  # preserve large integers as literal text
        c = WriteOnlyCell(ws, value=value)
        if isinstance(value, str):
            c.data_type = "s"  # formulas stored as literal strings, including headers
        return c
    ws.append([cell(c) for c in df.columns])
    for row in df.itertuples(index=False, name=None):
        ws.append([cell(v) for v in row])
    output = BytesIO()
    wb.save(output)
    return output.getvalue()
