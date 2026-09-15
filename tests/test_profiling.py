import numpy as np
import pandas as pd
import pytest
from datatriage.profiling import overview, column_profile, inferred_type, outlier_mask


def test_numeric_statistics_use_finite_values_only():
    result = column_profile(pd.Series([1, 2, 3, 4, np.inf, None]))
    assert result["mean"] == 2.5
    assert result["median"] == 2.5
    assert result["q1"] == 1.75
    assert result["q3"] == 3.25
    assert result["std"] == pytest.approx(1.2909944487)
    assert result["missing"] == 1
    assert result["finite_count"] == 4


def test_text_profile():
    result = column_profile(pd.Series(["a", "long", "a", None]))
    assert result["unique"] == 2
    assert result["minimum_length"] == 1
    assert result["maximum_length"] == 4
    assert result["average_length"] == 2
    assert result["common_values"][0] == {"value": "a", "count": 2}


def test_all_null_statistics():
    result = column_profile(pd.Series([None, None]))
    assert result["type"] == "empty"
    assert result["missing_percentage"] == 100


@pytest.mark.parametrize("values,kind", [(["01", "02"], "numeric"), ([True, False], "boolean"),
                                       (["a", "b"], "text"), ([1, "bad"], "text")])
def test_suggested_types(values, kind):
    assert inferred_type(pd.Series(values)) == kind


def test_datetime_profile():
    s = pd.Series(pd.to_datetime(["2024-01-01", "2024-02-01"]))
    result = column_profile(s)
    assert result["type"] == "datetime"
    assert result["minimum"] == "2024-01-01T00:00:00"


def test_overview_and_no_divide_by_zero():
    df = pd.DataFrame({"a": [1, 1, None], "b": ["x", "x", "y"]})
    result = overview(df)
    assert result["duplicate_rows"] == 1
    assert result["missing_cells"] == 1
    assert result["missing_percentage"] == pytest.approx(100 / 6)
    assert overview(df.iloc[:0])["missing_percentage"] == 0


def test_iqr_handles_small_and_zero_spread():
    assert not outlier_mask(pd.Series([1, 1, 100])).any()
    assert outlier_mask(pd.Series([1, 1, 1, 1, 100])).tolist() == [False, False, False, False, True]
