# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Evaluate & Promote Model
# MAGIC
# MAGIC **What this does:**
# MAGIC Loads the latest registered `PriceOptimizationModel` version, runs it against a
# MAGIC held-out validation set, checks quality gates (RMSE + MAPE thresholds), and
# MAGIC auto-promotes to Production if all gates pass.
# MAGIC
# MAGIC **Quality gates (configurable via widgets):**
# MAGIC - `max_rmse` — maximum allowed RMSE on validation set
# MAGIC - `max_mape` — maximum allowed MAPE % on validation set
# MAGIC
# MAGIC **Run:** Immediately after `05_train_price_model.py` in the training pipeline.

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

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_metrics, passes_quality_gate
from src.features.definitions import ALL_FEATURE_COLS, TARGET_COL
from src.utils.mlflow_utils import MODEL_NAME, get_latest_model_version, promote_model

# COMMAND ----------
# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("max_rmse",         "10.0", "Maximum allowed RMSE (quality gate)")
dbutils.widgets.text("max_mape",         "15.0", "Maximum allowed MAPE % (quality gate)")
dbutils.widgets.text("min_history_days", "7",    "Minimum days of history per ASIN")
dbutils.widgets.text("test_size",        "0.2",  "Validation split fraction")
dbutils.widgets.text("auto_promote",     "true", "Auto-promote to Production if gates pass")

MAX_RMSE         = float(dbutils.widgets.get("max_rmse"))
MAX_MAPE         = float(dbutils.widgets.get("max_mape"))
MIN_HISTORY_DAYS = int(dbutils.widgets.get("min_history_days"))
TEST_SIZE        = float(dbutils.widgets.get("test_size"))
AUTO_PROMOTE     = dbutils.widgets.get("auto_promote").lower() == "true"

print(f"Quality gates : RMSE ≤ {MAX_RMSE}  |  MAPE ≤ {MAX_MAPE}%")
print(f"Auto-promote  : {AUTO_PROMOTE}")

# COMMAND ----------
# MAGIC %md ## Load latest registered model

# COMMAND ----------

latest = get_latest_model_version(stage="None")
print(f"Evaluating {MODEL_NAME} v{latest.version}  (run_id: {latest.run_id})")

model_uri = f"models:/{MODEL_NAME}/{latest.version}"
model = mlflow.xgboost.load_model(model_uri)

# COMMAND ----------
# MAGIC %md ## Load and prepare validation data

# COMMAND ----------

raw = spark.table("gold.price_features").toPandas()
raw = raw.dropna(subset=[TARGET_COL, "current_price", "comp_median_price"])

asin_counts = raw.groupby("asin")["scrape_date"].count()
valid_asins = asin_counts[asin_counts >= MIN_HISTORY_DAYS].index
df = raw[raw["asin"].isin(valid_asins)].copy().sort_values("scrape_date")

df["day_of_week"] = pd.to_datetime(df["scrape_date"]).dt.dayofweek
df["price_to_median_ratio"] = df["current_price"] / df["comp_median_price"].replace(0, np.nan)

for col in ALL_FEATURE_COLS:
    if col in df.columns:
        df[col] = df[col].fillna(df[col].median())

split_idx = int(len(df) * (1 - TEST_SIZE))
X_val = df[ALL_FEATURE_COLS].astype(float).iloc[split_idx:]
y_val = df[TARGET_COL].astype(float).iloc[split_idx:]

print(f"Validation rows : {len(X_val)}")

# COMMAND ----------
# MAGIC %md ## Run evaluation

# COMMAND ----------

preds   = model.predict(X_val)
metrics = compute_metrics(y_val, preds)

print(f"RMSE : {metrics['rmse']:.4f}")
print(f"MAE  : {metrics['mae']:.4f}")
print(f"MAPE : {metrics['mape']:.2f}%")

residuals = pd.DataFrame({
    "asin":      df.iloc[split_idx:]["asin"].values,
    "date":      df.iloc[split_idx:]["scrape_date"].values,
    "actual":    y_val.values,
    "predicted": preds,
    "error":     y_val.values - preds,
})
print("\nWorst predictions (largest absolute error):")
print(residuals.assign(abs_error=residuals["error"].abs()).nlargest(5, "abs_error").to_string(index=False))

# COMMAND ----------
# MAGIC %md ## Quality gate check

# COMMAND ----------

passed, message = passes_quality_gate(metrics, max_rmse=MAX_RMSE, max_mape=MAX_MAPE)

if passed:
    print(f"✓ {message}")
    if AUTO_PROMOTE:
        promote_model(latest.version, target_stage="Production")
    else:
        print(f"Auto-promote disabled. Manually promote v{latest.version} when ready.")
else:
    error_msg = f"Quality gate FAILED: {message}"
    print(f"✗ {error_msg}")
    raise ValueError(error_msg)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC If promoted, the model is now live at `models:/PriceOptimizationModel/Production`.
# MAGIC Next step: run `07_batch_scoring.py` to score today's gold features.
