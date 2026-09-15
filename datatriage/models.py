"""Small serializable models shared by the engine and UI."""
from dataclasses import dataclass, field
from typing import Any
import pandas as pd


@dataclass(frozen=True)
class Rule:
    column: str
    kind: str  # numeric, date, identifier, range
    date_format: str = "%Y-%m-%d"
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class Settings:
    iqr_multiplier: float = 1.5
    almost_empty: float = 0.95
    rules: tuple[Rule, ...] = ()


@dataclass(frozen=True)
class Issue:
    kind: str
    column: str | None
    severity: str
    affected_count: int
    percentage: float
    explanation: str
    suggested_action: str
    rows: tuple[int, ...] = ()  # zero-based positions; capped for display
    unit: str = "cells"


@dataclass
class LoadedData:
    frame: pd.DataFrame
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Action:
    kind: str
    column: str | None = None
    value: Any = None


@dataclass
class CleaningResult:
    frame: pd.DataFrame
    log: list[dict]
    rows_removed: int
    columns_removed: int
    cells_modified: int
