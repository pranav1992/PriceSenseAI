import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import numpy as np
import pytest

from src.evaluation.metrics import compute_metrics, passes_quality_gate


def test_perfect_predictions():
    y = np.array([100.0, 200.0, 150.0])
    metrics = compute_metrics(y, y)
    assert metrics["rmse"] == pytest.approx(0.0)
    assert metrics["mae"] == pytest.approx(0.0)
    assert metrics["mape"] == pytest.approx(0.0)


def test_metrics_non_negative():
    y_true = np.array([50.0, 100.0, 200.0])
    y_pred = np.array([55.0, 90.0, 210.0])
    metrics = compute_metrics(y_true, y_pred)
    assert metrics["rmse"] >= 0
    assert metrics["mae"] >= 0
    assert metrics["mape"] >= 0


def test_quality_gate_passes():
    metrics = {"rmse": 1.5, "mae": 1.0, "mape": 3.0}
    passed, msg = passes_quality_gate(metrics, max_rmse=5.0, max_mape=10.0)
    assert passed
    assert "passed" in msg.lower()


def test_quality_gate_fails_rmse():
    metrics = {"rmse": 10.0, "mae": 5.0, "mape": 8.0}
    passed, msg = passes_quality_gate(metrics, max_rmse=5.0)
    assert not passed
    assert "RMSE" in msg


def test_quality_gate_fails_mape():
    metrics = {"rmse": 1.0, "mae": 0.5, "mape": 25.0}
    passed, msg = passes_quality_gate(metrics, max_mape=15.0)
    assert not passed
    assert "MAPE" in msg


def test_quality_gate_no_thresholds():
    metrics = {"rmse": 999.0, "mae": 999.0, "mape": 999.0}
    passed, _ = passes_quality_gate(metrics)
    assert passed
