"""Bound work and reject invalid settings before expensive operations."""
import math
import pandas as pd
from .models import Settings

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 50_000
MAX_COLUMNS = 200
MAX_CELLS = 2_000_000
MAX_UNZIPPED_BYTES = 50 * 1024 * 1024


def validate_frame(df: pd.DataFrame) -> None:
    if len(df) > MAX_ROWS or len(df.columns) > MAX_COLUMNS or df.size > MAX_CELLS:
        raise ValueError("Dataset exceeds limits: 50,000 rows, 200 columns or 2 million cells.")
    if not df.columns.is_unique or any(not isinstance(c, str) for c in df.columns):
        raise ValueError("Column names must be unique strings.")


def validate_settings(df: pd.DataFrame, settings: Settings) -> None:
    if not math.isfinite(settings.iqr_multiplier) or not 0.5 <= settings.iqr_multiplier <= 5:
        raise ValueError("IQR multiplier must be between 0.5 and 5.")
    if not 0 < settings.almost_empty <= 1:
        raise ValueError("Almost-empty threshold must be in (0, 1].")
    for rule in settings.rules:
        if rule.column not in df:
            raise ValueError(f"Rule refers to an unknown column: {rule.column}")
        if rule.kind not in {"numeric", "date", "identifier", "range"}:
            raise ValueError("Unsupported rule.")
        if rule.kind == "date" and not rule.date_format:
            raise ValueError("Choose an explicit date format.")
        if any(x is not None and not math.isfinite(x) for x in (rule.minimum, rule.maximum)):
            raise ValueError("Range bounds must be finite.")
        if rule.minimum is not None and rule.maximum is not None and rule.minimum > rule.maximum:
            raise ValueError("Minimum cannot exceed maximum.")
