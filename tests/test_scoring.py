import pandas as pd
import pytest
from datatriage.detectors import detect_issues
from datatriage.scoring import quality_score
from datatriage.models import Settings, Rule


def test_clean_score_and_empty():
    df = pd.DataFrame({"id": ["A", "B"], "value": [2, 4]})
    assert quality_score(df, detect_issues(df))["overall"] == 100
    assert quality_score(df.iloc[:0], [])["overall"] is None


def test_exact_formula_and_overlap():
    df = pd.DataFrame({"text": [" a ", "a"], "number": [None, 3]})
    result = quality_score(df, detect_issues(df))
    # Whitespace + category variance overlaps at row 0, counting 2 distinct cells.
    assert result["components"] == {"Completeness": 75, "Uniqueness": 100, "Validity": 100, "Consistency": 50}
    assert result["overall"] == 81.25


def test_validity_union_not_double_penalty():
    df = pd.DataFrame({"n": ["bad", "2"]})
    settings = Settings(rules=(Rule("n", "numeric"), Rule("n", "range", minimum=0)))
    score = quality_score(df, detect_issues(df, settings))
    assert score["components"]["Validity"] == 50


@pytest.mark.parametrize("size", [1, 2, 20, 100])
def test_poor_dataset_bounded_deterministic(size):
    df = pd.DataFrame({"a": [None] * size, "b": [" x "] * size})
    first = quality_score(df, detect_issues(df))
    assert first == quality_score(df, detect_issues(df))
    assert 0 <= first["overall"] < 100
    assert all(0 <= v <= 100 for v in first["components"].values())
