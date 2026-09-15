import pandas as pd
import numpy as np
import pytest
from pandas.testing import assert_frame_equal
from datatriage.cleaning import clean
from datatriage.models import Action


def test_ordered_plan_copy_and_net_counts():
    df = pd.DataFrame({"name": [" a ", "a", None], "n": [1, 1, None]})
    untouched = df.copy(deep=True)
    result = clean(df, [Action("trim", "name"), Action("remove_duplicates"), Action("remove_empty_rows")])
    assert_frame_equal(df, untouched)
    assert result.frame.iloc[0].tolist() == ["a", 1]
    assert result.rows_removed == 2
    assert result.cells_modified == 1
    assert [x["rows_removed"] for x in result.log] == [0, 1, 1]


@pytest.mark.parametrize("kind,expected", [("fill_median", 2), ("fill_mean", 4)])
def test_numeric_filling(kind, expected):
    df = pd.DataFrame({"n": [1, 2, 9, None]})
    result = clean(df, [Action(kind, "n")])
    assert result.frame.iloc[-1, 0] == expected
    assert result.cells_modified == 1


def test_mode_tie_uses_first_appearance():
    result = clean(pd.DataFrame({"s": ["b", "a", None]}), [Action("fill_mode", "s")])
    assert result.frame.iloc[-1, 0] == "b"


def test_custom_fill_and_blank_conversion():
    df = pd.DataFrame({"s": [" ", "", None, "a"]})
    result = clean(df, [Action("blank_to_null", "s"), Action("fill_custom", "s", "Unknown")])
    assert result.frame["s"].tolist() == ["Unknown", "Unknown", "Unknown", "a"]
    assert result.log[0]["new_missing_cells"] == 2
    assert result.cells_modified == 3


def test_column_and_empty_removal():
    df = pd.DataFrame({"a": [None], "b": [1], "c": [2]})
    result = clean(df, [Action("remove_empty_columns"), Action("drop_column", "c")])
    assert result.frame.columns.tolist() == ["b"]
    assert result.columns_removed == 2


def test_conversions_and_information_loss_count():
    df = pd.DataFrame({"n": ["001", "bad"], "d": ["31/12/2024", "invalid"]})
    result = clean(df, [Action("to_numeric", "n"), Action("to_datetime", "d", "%d/%m/%Y")])
    assert result.frame.loc[0, "n"] == 1
    assert result.frame.loc[0, "d"] == pd.Timestamp("2024-12-31")
    assert result.frame.iloc[1].isna().all()
    assert [x["new_missing_cells"] for x in result.log] == [1, 1]


def test_lowercase_and_outlier_removal():
    df = pd.DataFrame({"n": [1, 1, 1, 1, 100], "s": ["A"] * 5})
    result = clean(df, [Action("lowercase", "s"), Action("remove_outliers", "n", 1.5)])
    assert len(result.frame) == 4
    assert result.frame["s"].tolist() == ["a"] * 4


@pytest.mark.parametrize("action", [Action("nope"), Action("trim", "missing"), Action("fill_median", "a"),
                                    Action("fill_custom", "a", ""), Action("remove_outliers", "a", 20)])
def test_invalid_plans_do_not_mutate(action):
    df = pd.DataFrame({"a": ["x", None]})
    before = df.copy(deep=True)
    with pytest.raises(ValueError):
        clean(df, [Action("trim", "a"), action])
    assert_frame_equal(df, before)


@pytest.mark.parametrize("kind", ["fill_mean", "fill_median", "fill_mode"])
def test_all_missing_cannot_invent_statistics(kind):
    with pytest.raises(ValueError):
        clean(pd.DataFrame({"a": [None, None]}), [Action(kind, "a")])


def test_empty_and_duplicate_index_inputs():
    df = pd.DataFrame({"a": [1, 1]}, index=[4, 4])
    result = clean(df, [Action("remove_duplicates")])
    assert result.rows_removed == 1
    assert clean(df.iloc[:0], []).cells_modified == 0


def test_dtype_only_not_counted_as_value_change():
    result = clean(pd.DataFrame({"a": [1, 2]}), [Action("to_numeric", "a")])
    assert result.cells_modified == 0


def test_actions_after_dropped_column_fail():
    with pytest.raises(ValueError, match="removed"):
        clean(pd.DataFrame({"a": [1]}), [Action("drop_column", "a"), Action("trim", "a")])
