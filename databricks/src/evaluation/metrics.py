import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


def compute_metrics(y_true: pd.Series | np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    with np.errstate(divide="ignore", invalid="ignore"):
        mape = float(np.nanmean(np.abs((y_true - y_pred) / np.where(y_true == 0, np.nan, y_true))) * 100)
    return {"rmse": rmse, "mae": mae, "mape": mape}


def passes_quality_gate(
    metrics: dict[str, float],
    max_rmse: float | None = None,
    max_mape: float | None = None,
) -> tuple[bool, str]:
    if max_rmse is not None and metrics["rmse"] > max_rmse:
        return False, f"RMSE {metrics['rmse']:.4f} exceeds threshold {max_rmse}"
    if max_mape is not None and metrics["mape"] > max_mape:
        return False, f"MAPE {metrics['mape']:.2f}% exceeds threshold {max_mape}%"
    return True, "All quality gates passed"
