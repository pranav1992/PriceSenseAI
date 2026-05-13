"""
End-to-end pipeline integration tests.

These tests require a running Spark/Databricks session and populated Delta tables.
Run with:  pytest -m integration databricks/tests/integration/
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest

from src.features.definitions import ALL_FEATURE_COLS, FEATURE_COLS, TARGET_COL
from src.evaluation.metrics import compute_metrics, passes_quality_gate


@pytest.mark.integration
def test_gold_features_schema(spark):
    """gold.price_features must contain all expected feature columns."""
    df = spark.table("gold.price_features")
    missing = [c for c in FEATURE_COLS + [TARGET_COL] if c not in df.columns]
    assert not missing, f"Missing columns in gold.price_features: {missing}"


@pytest.mark.integration
def test_gold_features_no_duplicate_keys(spark):
    """Each (asin, scrape_date) must be unique in gold.price_features."""
    from pyspark.sql import functions as F
    df = spark.table("gold.price_features")
    dupes = (
        df.groupBy("asin", "scrape_date")
        .count()
        .filter(F.col("count") > 1)
        .count()
    )
    assert dupes == 0, f"Found {dupes} duplicate (asin, scrape_date) keys in gold.price_features"


@pytest.mark.integration
def test_predictions_table_populated(spark):
    """gold.price_predictions must exist and have at least one row."""
    df = spark.table("gold.price_predictions")
    assert df.count() > 0, "gold.price_predictions is empty"


@pytest.mark.integration
def test_predictions_schema(spark):
    """gold.price_predictions must have expected columns."""
    df = spark.table("gold.price_predictions")
    expected = ["asin", "scrape_date", "predicted_price", "current_price", "model_version"]
    missing = [c for c in expected if c not in df.columns]
    assert not missing, f"Missing columns in gold.price_predictions: {missing}"


@pytest.mark.integration
def test_metrics_on_predictions(spark):
    """Rolling MAPE on recent predictions should be within acceptable range."""
    predictions = (
        spark.table("gold.price_predictions")
        .toPandas()
    )
    if predictions.empty:
        pytest.skip("No predictions available")

    metrics = compute_metrics(predictions["current_price"], predictions["predicted_price"].values)
    passed, msg = passes_quality_gate(metrics, max_mape=50.0)
    assert passed, f"Pipeline integration metrics failed: {msg}"
