# Databricks notebook source
# MAGIC %md
# MAGIC # 08 — Data Drift Detection
# MAGIC
# MAGIC **What this does:**
# MAGIC Compares today's feature distributions in `gold.price_features` against a 30-day
# MAGIC baseline using the Kolmogorov-Smirnov test. Flags features whose distributions
# MAGIC have shifted significantly — an early warning that model accuracy may degrade.
# MAGIC
# MAGIC **Approach:**
# MAGIC - Baseline: rows from the past `lookback_days` (default 30)
# MAGIC - Current: today's rows
# MAGIC - Test: KS test per feature; alert if p-value < threshold (default 0.05)
# MAGIC - Also checks mean drift % as a simpler fallback metric
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

from datetime import datetime, timedelta, timezone

import pandas as pd
from pyspark.sql import functions as F
from scipy import stats

from src.features.definitions import FEATURE_COLS

# COMMAND ----------
# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("scrape_date",       "",    "Reference date (YYYY-MM-DD, blank = today UTC)")
dbutils.widgets.text("lookback_days",     "30",  "Baseline window in days")
dbutils.widgets.text("ks_pvalue_thresh",  "0.05","KS test p-value alert threshold")
dbutils.widgets.text("mean_drift_thresh", "20.0","Max allowed mean drift % per feature")

SCRAPE_DATE      = dbutils.widgets.get("scrape_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
LOOKBACK_DAYS    = int(dbutils.widgets.get("lookback_days"))
KS_PVAL_THRESH   = float(dbutils.widgets.get("ks_pvalue_thresh"))
MEAN_DRIFT_THRESH= float(dbutils.widgets.get("mean_drift_thresh"))

baseline_start = (datetime.strptime(SCRAPE_DATE, "%Y-%m-%d") - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

print(f"Reference date  : {SCRAPE_DATE}")
print(f"Baseline window : {baseline_start} → {SCRAPE_DATE} ({LOOKBACK_DAYS} days)")
print(f"KS p-value alert: < {KS_PVAL_THRESH}")
print(f"Mean drift alert: > {MEAN_DRIFT_THRESH}%")

# COMMAND ----------
# MAGIC %md ## Load baseline and current distributions

# COMMAND ----------

baseline_df = (
    spark.table("gold.price_features")
    .filter(F.col("scrape_date") >= F.lit(baseline_start))
    .filter(F.col("scrape_date") < F.lit(SCRAPE_DATE))
    .select(FEATURE_COLS)
    .toPandas()
    .dropna()
)

current_df = (
    spark.table("gold.price_features")
    .filter(F.col("scrape_date") == F.lit(SCRAPE_DATE))
    .select(FEATURE_COLS)
    .toPandas()
    .dropna()
)

print(f"Baseline rows : {len(baseline_df)}")
print(f"Current rows  : {len(current_df)}")

if baseline_df.empty or current_df.empty:
    print("WARNING: Not enough data for drift analysis. Skipping.")
    dbutils.notebook.exit("skipped — insufficient data")

# COMMAND ----------
# MAGIC %md ## KS test per feature

# COMMAND ----------

results = []
for col in FEATURE_COLS:
    if col not in baseline_df.columns or col not in current_df.columns:
        continue
    ks_stat, p_value = stats.ks_2samp(baseline_df[col].dropna(), current_df[col].dropna())
    baseline_mean = baseline_df[col].mean()
    current_mean  = current_df[col].mean()
    mean_drift_pct = (
        abs(current_mean - baseline_mean) / abs(baseline_mean) * 100
        if baseline_mean != 0 else 0.0
    )
    drifted = (p_value < KS_PVAL_THRESH) or (mean_drift_pct > MEAN_DRIFT_THRESH)
    results.append({
        "feature":        col,
        "ks_statistic":   round(ks_stat, 4),
        "p_value":        round(p_value, 4),
        "baseline_mean":  round(baseline_mean, 4),
        "current_mean":   round(current_mean, 4),
        "mean_drift_pct": round(mean_drift_pct, 2),
        "drifted":        drifted,
    })

drift_df = pd.DataFrame(results).sort_values("drifted", ascending=False)
print(drift_df.to_string(index=False))

# COMMAND ----------
# MAGIC %md ## Alert on drifted features

# COMMAND ----------

drifted_features = drift_df[drift_df["drifted"]]

if drifted_features.empty:
    print("✓ No significant data drift detected")
else:
    print(f"⚠ DRIFT DETECTED in {len(drifted_features)} feature(s):")
    print(drifted_features[["feature", "ks_statistic", "p_value", "mean_drift_pct"]].to_string(index=False))
    print("\nConsider: re-training the model or investigating upstream data quality.")

# COMMAND ----------
# MAGIC %md ## Log drift summary to MLflow

# COMMAND ----------

import mlflow

mlflow.set_experiment("/Shared/pricesense-ai/monitoring")

with mlflow.start_run(run_name=f"data_drift_{SCRAPE_DATE}"):
    mlflow.log_param("scrape_date", SCRAPE_DATE)
    mlflow.log_param("lookback_days", LOOKBACK_DAYS)
    mlflow.log_metric("drifted_feature_count", len(drifted_features))
    for _, row in drift_df.iterrows():
        mlflow.log_metric(f"ks_{row['feature']}", row["ks_statistic"])
        mlflow.log_metric(f"drift_pct_{row['feature']}", row["mean_drift_pct"])

print("✓ Drift metrics logged to MLflow monitoring experiment")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC Next step: run `09_model_performance.py` to track prediction accuracy over time.
