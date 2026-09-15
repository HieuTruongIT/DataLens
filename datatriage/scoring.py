"""A documented diagnostic heuristic; overlapping issues count once per cell."""
import pandas as pd
from .models import Issue

VALIDITY = {"invalid_date", "invalid_numeric", "range_violation", "infinite"}
CONSISTENCY = {"whitespace", "blank_text", "category_variants", "mixed_types", "mixed_numeric_text", "mixed_date_formats"}


def quality_score(df: pd.DataFrame, issues: list[Issue]) -> dict:
    if not df.size:
        return {"overall": None, "components": {k: None for k in ("Completeness", "Uniqueness", "Validity", "Consistency")}}
    def cell_count(kinds):
        return len({(issue.column, row) for issue in issues if issue.kind in kinds and issue.column in df for row in issue.rows})
    components = {
        "Completeness": 100 * (1 - df.isna().sum().sum() / df.size),
        "Uniqueness": 100 * (1 - df.duplicated().sum() / len(df)),
        "Validity": 100 * (1 - cell_count(VALIDITY) / df.size),
        "Consistency": 100 * (1 - cell_count(CONSISTENCY) / df.size),
    }
    overall = sum(components.values()) / 4
    return {"overall": round(float(overall), 2), "components": {k: round(float(max(0, min(100, v))), 2) for k, v in components.items()}}
