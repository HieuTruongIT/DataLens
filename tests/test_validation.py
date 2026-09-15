import pandas as pd
import pytest
from datatriage.models import Settings, Rule
from datatriage.validation import validate_frame, validate_settings


@pytest.mark.parametrize("settings", [Settings(0), Settings(float("nan")), Settings(6), Settings(almost_empty=0),
                                      Settings(rules=(Rule("missing", "numeric"),)), Settings(rules=(Rule("a", "unknown"),)),
                                      Settings(rules=(Rule("a", "range", minimum=3, maximum=1),)),
                                      Settings(rules=(Rule("a", "range", maximum=float("inf")),))])
def test_bad_settings(settings):
    with pytest.raises(ValueError):
        validate_settings(pd.DataFrame({"a": [1]}), settings)


def test_duplicate_names_rejected_by_engine():
    with pytest.raises(ValueError, match="unique"):
        validate_frame(pd.DataFrame([[1, 2]], columns=["a", "a"]))


def test_max_columns():
    with pytest.raises(ValueError, match="limits"):
        validate_frame(pd.DataFrame(columns=[str(i) for i in range(201)]))
