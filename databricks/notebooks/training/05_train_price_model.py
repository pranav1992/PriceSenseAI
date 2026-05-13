# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Train Price Optimisation Model
# MAGIC
# MAGIC **What this does:**
# MAGIC Loads features from `gold.price_features`, engineers additional signals, and trains
# MAGIC an XGBoost regressor to predict `suggested_price`. Every run is tracked in MLflow
# MAGIC and the model is registered in the Model Registry under `PriceOptimizationModel`.
# MAGIC
# MAGIC **Problem framing:**
# MAGIC - Input (X): time-series + competitive features from `gold.price_features`
# MAGIC - Target (y): `suggested_price` (competitor-median-anchored with rating premium)
# MAGIC - Split: time-based (oldest rows train, newest rows test) to prevent future leakage
# MAGIC
# MAGIC **Run:** Weekly (Monday 02:00 UTC) via Databricks Workflow, after `gold_features` task.

# COMMAND ----------
# MAGIC %md ## Install dependencies

# COMMAND ----------

# %pip install xgboost scikit-learn mlflow shap
# dbutils.library.restartPython()

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
from mlflow.models.signature import infer_signature

from src.evaluation.metrics import compute_metrics
from src.features.definitions import ALL_FEATURE_COLS, TARGET_COL
from src.features.validation import check_minimum_rows, check_required_columns
from src.models.hyperparams import DEFAULT_PARAMS
from src.models.price_optimizer import PriceOptimizer
from src.utils.mlflow_utils import EXPERIMENT_PATH, MODEL_NAME

# COMMAND ----------
# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("test_size",        "0.2",  "Test split fraction (0.0–0.5)")
dbutils.widgets.text("n_estimators",     "200",  "XGBoost n_estimators")
dbutils.widgets.text("max_depth",        "4",    "XGBoost max_depth")
dbutils.widgets.text("learning_rate",    "0.05", "XGBoost learning_rate")
dbutils.widgets.text("min_history_days", "7",    "Minimum days of history required per ASIN")

TEST_SIZE        = float(dbutils.widgets.get("test_size"))
MIN_HISTORY_DAYS = int(dbutils.widgets.get("min_history_days"))

params = {
    **DEFAULT_PARAMS,
    "n_estimators":  int(dbutils.widgets.get("n_estimators")),
    "max_depth":     int(dbutils.widgets.get("max_depth")),
    "learning_rate": float(dbutils.widgets.get("learning_rate")),
}

print(f"Test size        : {TEST_SIZE}")
print(f"min_history_days : {MIN_HISTORY_DAYS}")
print(f"Params           : {params}")

# COMMAND ----------
# MAGIC %md ## Load and validate features

# COMMAND ----------

raw = spark.table("gold.price_features").toPandas()

check_required_columns(raw, [TARGET_COL, "current_price", "comp_median_price", "asin", "scrape_date"])
raw = raw.dropna(subset=[TARGET_COL, "current_price", "comp_median_price"])

asin_counts = raw.groupby("asin")["scrape_date"].count()
valid_asins = asin_counts[asin_counts >= MIN_HISTORY_DAYS].index
df = raw[raw["asin"].isin(valid_asins)].copy()

check_minimum_rows(df, 10, context=f"— run the scraper daily for at least {MIN_HISTORY_DAYS} days")

print(f"Total rows   : {len(df)}")
print(f"Unique ASINs : {df['asin'].nunique()}")
print(f"Date range   : {df['scrape_date'].min()} → {df['scrape_date'].max()}")

# COMMAND ----------
# MAGIC %md ## Feature engineering

# COMMAND ----------

df = df.sort_values(["asin", "scrape_date"])
df["day_of_week"] = pd.to_datetime(df["scrape_date"]).dt.dayofweek
df["price_to_median_ratio"] = df["current_price"] / df["comp_median_price"].replace(0, np.nan)

for col in ALL_FEATURE_COLS:
    if col in df.columns:
        df[col] = df[col].fillna(df[col].median())

X = df[ALL_FEATURE_COLS].astype(float)
y = df[TARGET_COL].astype(float)

print(f"Feature matrix : {X.shape}")
print(X.describe().T[["mean", "std", "min", "max"]])

# COMMAND ----------
# MAGIC %md ## Time-based train / test split
# MAGIC
# MAGIC Oldest rows train, newest rows test — prevents future price leakage.

# COMMAND ----------

df_sorted = df.sort_values("scrape_date")
split_idx = int(len(df_sorted) * (1 - TEST_SIZE))

X_train = X.loc[df_sorted.index[:split_idx]]
X_test  = X.loc[df_sorted.index[split_idx:]]
y_train = y.loc[df_sorted.index[:split_idx]]
y_test  = y.loc[df_sorted.index[split_idx:]]

print(f"Train rows: {len(X_train)}  |  Test rows: {len(X_test)}")

# COMMAND ----------
# MAGIC %md ## Train with MLflow tracking

# COMMAND ----------

mlflow.set_experiment(EXPERIMENT_PATH)

run_name = f"xgboost_d{params['max_depth']}_lr{params['learning_rate']}_n{params['n_estimators']}"

with mlflow.start_run(run_name=run_name) as run:
    mlflow.log_params(params)

    optimizer = PriceOptimizer(params)
    optimizer.fit(X_train, y_train, X_val=X_test, y_val=y_test)

    preds   = optimizer.predict(X_test)
    metrics = compute_metrics(y_test, preds)

    mlflow.log_metrics(metrics)
    print(f"RMSE : {metrics['rmse']:.4f}")
    print(f"MAE  : {metrics['mae']:.4f}")
    print(f"MAPE : {metrics['mape']:.2f}%")

    importances = optimizer.feature_importances(ALL_FEATURE_COLS)
    print("\nTop feature importances:")
    print(importances.head(10))
    mlflow.log_dict(importances.to_dict(), "feature_importances.json")

    signature = infer_signature(X_train, preds)
    mlflow.xgboost.log_model(
        optimizer.model,
        artifact_path="model",
        signature=signature,
        input_example=X_train.head(3),
        registered_model_name=MODEL_NAME,
    )

    run_id = run.info.run_id
    print(f"\nMLflow run ID : {run_id}")
    print(f"Model         : {MODEL_NAME} (registered, pending evaluation in 06_evaluate_model)")

# COMMAND ----------
# MAGIC %md ## SHAP feature explanations

# COMMAND ----------

try:
    import shap
    explainer  = shap.TreeExplainer(optimizer.model)
    shap_vals  = explainer.shap_values(X_test)
    shap_df    = pd.DataFrame(shap_vals, columns=ALL_FEATURE_COLS)
    shap_means = shap_df.abs().mean().sort_values(ascending=False)
    print("Mean |SHAP| values (feature impact ranking):")
    print(shap_means.to_string())
except ImportError:
    print("SHAP not installed — run %pip install shap to enable explanations")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC The model is registered in the MLflow Model Registry under `PriceOptimizationModel`.
# MAGIC Next step: run `06_evaluate_model.py` to validate metrics and promote to Production.
