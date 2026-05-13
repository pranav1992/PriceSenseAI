import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pandas as pd
import pytest

from src.features.definitions import ALL_FEATURE_COLS, FEATURE_COLS, TARGET_COL
from src.features.validation import (
    check_feature_completeness,
    check_minimum_rows,
    check_null_fraction,
    check_required_columns,
)


def test_feature_cols_non_empty():
    assert len(FEATURE_COLS) > 0


def test_all_feature_cols_includes_engineered():
    assert "day_of_week" in ALL_FEATURE_COLS
    assert "price_to_median_ratio" in ALL_FEATURE_COLS


def test_target_col_defined():
    assert TARGET_COL == "suggested_price"


def test_check_required_columns_passes():
    df = pd.DataFrame(columns=FEATURE_COLS + [TARGET_COL])
    check_required_columns(df, FEATURE_COLS)


def test_check_required_columns_raises():
    df = pd.DataFrame(columns=["price"])
    with pytest.raises(ValueError, match="Missing required columns"):
        check_required_columns(df, ["price", "missing_col"])


def test_check_minimum_rows_passes():
    df = pd.DataFrame({"a": range(10)})
    check_minimum_rows(df, 5)


def test_check_minimum_rows_raises():
    df = pd.DataFrame({"a": range(3)})
    with pytest.raises(ValueError):
        check_minimum_rows(df, 10)


def test_check_null_fraction_passes():
    df = pd.DataFrame({"price": [1.0, 2.0, 3.0, None]})
    check_null_fraction(df, "price", max_null_fraction=0.5)


def test_check_null_fraction_raises():
    df = pd.DataFrame({"price": [None, None, None, 1.0]})
    with pytest.raises(ValueError, match="nulls"):
        check_null_fraction(df, "price", max_null_fraction=0.5)
