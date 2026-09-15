import numpy as np
import pandas as pd
from datatriage.detectors import detect_issues
from datatriage.models import Rule, Settings


def lookup(df, settings=Settings()):
    return {(i.kind, i.column): i for i in detect_issues(df, settings)}


def test_missing_duplicate_constant_empty_and_whitespace():
    df = pd.DataFrame({"name": [" a ", " a ", None], "empty": [None] * 3, "constant": [4] * 3})
    result = lookup(df)
    assert result["duplicate_rows", None].affected_count == 1
    assert result["whitespace", "name"].rows == (0, 1)
    assert result["missing", "name"].severity == "HIGH"
    assert result["empty_column", "empty"].affected_count == 3
    assert result["constant", "constant"].severity == "INFO"


def test_almost_empty_and_category_variants():
    df = pd.DataFrame({"sparse": [None] * 19 + ["a"], "city": ["Astana", "astana"] * 10})
    result = lookup(df)
    assert result["almost_empty", "sparse"].affected_count == 19
    assert result["category_variants", "city"].affected_count == 20


def test_outliers_and_infinite_are_distinct():
    result = lookup(pd.DataFrame({"n": [1, 2, 3, 4, 5, 999, np.inf]}))
    assert result["outlier", "n"].rows == (5,)
    assert result["infinite", "n"].rows == (6,)


def test_configured_rules_do_not_guess_semantics():
    df = pd.DataFrame({"date": ["2024-01-02", "2024-02-30", "03/04/2024", None],
                       "id": ["01", "01", "02", None], "age": ["20", "-3", "bad", "140"]})
    result = lookup(df, Settings(rules=(Rule("date", "date"), Rule("id", "identifier"), Rule("age", "range", minimum=0, maximum=120), Rule("age", "numeric"))))
    assert result["invalid_date", "date"].rows == (1, 2)
    assert result["duplicate_identifier", "id"].rows == (0, 1)
    assert result["range_violation", "age"].rows == (1, 2, 3)
    assert result["invalid_numeric", "age"].rows == (2,)
    assert not any(i.kind == "invalid_date" for i in detect_issues(df))


def test_mixed_types_and_duplicate_columns():
    df = pd.DataFrame({"a": [1, "x"], "b": [1, "x"], "Unnamed: 0": [0, 1]})
    result = lookup(df)
    assert ("mixed_types", "a") in result
    assert ("duplicate_column", "b") in result
    assert ("index_like", "Unnamed: 0") in result


def test_duplicate_header_metadata():
    issues = detect_issues(pd.DataFrame({"a": ["1"]}), notes=['Duplicate column name "a" renamed to "a [2]" on import.'])
    assert any(i.kind == "duplicate_header" and i.unit == "columns" for i in issues)


def test_empty_dataset_no_row_findings():
    assert detect_issues(pd.DataFrame({"a": []})) == []


def test_nullable_csv_text_does_not_compare_na_as_boolean():
    df = pd.DataFrame({"text": [" a ", pd.NA, ""]})
    result = lookup(df)
    assert result["whitespace", "text"].rows == (0,)
    assert result["blank_text", "text"].rows == (2,)
