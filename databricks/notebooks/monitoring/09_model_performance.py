# Databricks notebook source
# MAGIC %md
# MAGIC # 09 — Model Performance Monitoring
# MAGIC
# MAGIC **What this does:**
# MAGIC Compares `gold.price_predictions` (model output) against actual prices in
# MAGIC `gold.price_features` over a rolling window. Tracks MAPE over time and raises
# MAGIC an alert if accuracy falls below the configured threshold.
# MAGIC
# MAGIC **Limitation:**
# MAGIC The model predicts `suggested_price` (optimal price), not `current_price`.
# MAGIC We use `current_price` as a proxy for "ground truth" here — a significant
# MAGIC divergence may indicate the market moved or the model is stale.
# MAGIC
# MAGIC **Run:** Daily (04:00 UTC) after batch scoring completes.

# COMMAND ----------
# MAGIC %md ## Setup

# COMMAND ----------

import sys

try:
    _nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    _parts = _nb.split("/")
    _dbt_idx = next(i for i, p in enumerate(_parts) if p == "databricks")
    _root = "/".join(_parts[: _dbt_idx + 1])
    if _root not in sys.path:
        sys.path.insert(0, _root)
except Exception:
    pass

from datetime import datetime, timezone

import mlflow
import numpy as np
import pandas as pd
from pyspark.sql import functions as F

from src.evaluation.metrics import compute_metrics

# COMMAND ----------
# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("scrape_date",      "",     "Reference date (YYYY-MM-DD, blank = today UTC)")
dbutils.widgets.text("lookback_days",    "7",    "Rolling window for performance tracking")
dbutils.widgets.text("mape_alert_pct",   "15.0", "MAPE % threshold to trigger alert")

SCRAPE_DATE     = dbutils.widgets.get("scrape_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
LOOKBACK_DAYS   = int(dbutils.widgets.get("lookback_days"))
MAPE_ALERT_PCT  = float(dbutils.widgets.get("mape_alert_pct"))

print(f"Reference date  : {SCRAPE_DATE}")
print(f"Lookback        : {LOOKBACK_DAYS} days")
print(f"MAPE alert at   : > {MAPE_ALERT_PCT}%")

# COMMAND ----------
# MAGIC %md ## Load predictions vs actuals

# COMMAND ----------

try:
    predictions = (
        spark.table("gold.price_predictions")
        .filter(F.col("scrape_date") <= F.lit(SCRAPE_DATE))
        .orderBy(F.col("scrape_date").desc())
        .limit(LOOKBACK_DAYS * 100)
        .toPandas()
    )
except Exception as e:
    print(f"gold.price_predictions not found: {e}")
    print("Run 07_batch_scoring.py first to populate predictions.")
    dbutils.notebook.exit("skipped — predictions table missing")

if predictions.empty:
    print("No predictions found in the lookback window. Skipping.")
    dbutils.notebook.exit("skipped — no predictions")

# COMMAND ----------
# MAGIC %md ## Compute rolling MAPE

# COMMAND ----------

predictions["scrape_date"] = pd.to_datetime(predictions["scrape_date"])
predictions = predictions.sort_values("scrape_date")

daily_metrics = []
for date, group in predictions.groupby("scrape_date"):
    if len(group) < 1:
        continue
    m = compute_metrics(group["current_price"], group["predicted_price"].values)
    daily_metrics.append({"date": date, **m, "n_asins": len(group)})

metrics_df = pd.DataFrame(daily_metrics)

if metrics_df.empty:
    print("No daily metrics computed. Skipping.")
    dbutils.notebook.exit("skipped — no metrics")

print("Daily performance:")
print(metrics_df.to_string(index=False))

rolling_mape = metrics_df["mape"].mean()
print(f"\nRolling {LOOKBACK_DAYS}-day avg MAPE : {rolling_mape:.2f}%")

# COMMAND ----------
# MAGIC %md ## Alert check

# COMMAND ----------

if rolling_mape > MAPE_ALERT_PCT:
    print(f"⚠ MODEL DEGRADATION: MAPE {rolling_mape:.2f}% exceeds threshold {MAPE_ALERT_PCT}%")
    print("Recommended action: trigger model retraining (run training_pipeline job).")
else:
    print(f"✓ Model performance healthy — MAPE {rolling_mape:.2f}% within threshold")

# COMMAND ----------
# MAGIC %md ## Log to MLflow monitoring experiment

# COMMAND ----------

mlflow.set_experiment("/Shared/pricesense-ai/monitoring")

with mlflow.start_run(run_name=f"model_perf_{SCRAPE_DATE}"):
    mlflow.log_param("scrape_date", SCRAPE_DATE)
    mlflow.log_param("lookback_days", LOOKBACK_DAYS)
    mlflow.log_metric("rolling_mape", rolling_mape)
    mlflow.log_metric("rolling_rmse", metrics_df["rmse"].mean())
    mlflow.log_metric("rolling_mae",  metrics_df["mae"].mean())
    mlflow.log_metric("alert_triggered", int(rolling_mape > MAPE_ALERT_PCT))

print("✓ Performance metrics logged to MLflow monitoring experiment")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC Daily monitoring complete. Check `/Shared/pricesense-ai/monitoring` in MLflow
# MAGIC to view the performance trend over time.
