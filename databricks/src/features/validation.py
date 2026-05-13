import pandas as pd


def check_required_columns(df: pd.DataFrame, required_cols: list[str]) -> None:
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def check_minimum_rows(df: pd.DataFrame, min_rows: int, context: str = "") -> None:
    if len(df) < min_rows:
        suffix = f" {context}" if context else ""
        raise ValueError(f"Only {len(df)} rows available (minimum {min_rows} required){suffix}")


def check_null_fraction(df: pd.DataFrame, col: str, max_null_fraction: float = 0.5) -> None:
    null_frac = df[col].isna().mean()
    if null_frac > max_null_fraction:
        raise ValueError(
            f"Column '{col}' has {null_frac:.1%} nulls — exceeds maximum {max_null_fraction:.1%}"
        )


def check_feature_completeness(df: pd.DataFrame, feature_cols: list[str], max_null_fraction: float = 0.5) -> None:
    for col in feature_cols:
        if col in df.columns:
            check_null_fraction(df, col, max_null_fraction)
