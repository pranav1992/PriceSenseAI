# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Price Optimisation Model
# MAGIC
# MAGIC **What this does:**
# MAGIC Trains an XGBoost model to predict the optimal (suggested) price for a product
# MAGIC given its time-series and competitive features. Every run is tracked in MLflow.
# MAGIC The best model is promoted to the Model Registry under `PriceOptimizationModel`.
# MAGIC
# MAGIC **Problem framing:**
# MAGIC - Input (X): time-series + competitive features from `gold.price_features`
# MAGIC - Target (y): `suggested_price` (competitor-median-anchored price with rating premium)
# MAGIC - Metric: RMSE and MAE on a held-out 20% test split
# MAGIC
# MAGIC **Why XGBoost here:**
# MAGIC Tabular features, low row count (one per ASIN per day), interpretable feature
# MAGIC importances, and fast iteration. Prophet / ARIMA would be used for per-ASIN
# MAGIC time-series decomposition (seasonality) — see the end of this notebook.
# MAGIC
# MAGIC **Run:** Manually or on a weekly schedule after enough history accumulates (≥30 days).

# COMMAND ----------
# MAGIC %md ## Install dependencies

# COMMAND ----------

# %pip install xgboost scikit-learn mlflow shap
# dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md ## Parameters

# COMMAND ----------

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from mlflow.models.signature import infer_signature
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

# COMMAND ----------

dbutils.widgets.text("test_size",     "0.2",  "Test split fraction (0.0–0.5)")
dbutils.widgets.text("n_estimators",  "200",  "XGBoost n_estimators")
dbutils.widgets.text("max_depth",     "4",    "XGBoost max_depth")
dbutils.widgets.text("learning_rate", "0.05", "XGBoost learning_rate")
dbutils.widgets.text("min_history_days", "7", "Minimum days of history required per ASIN")

TEST_SIZE         = float(dbutils.widgets.get("test_size"))
N_ESTIMATORS      = int(dbutils.widgets.get("n_estimators"))
MAX_DEPTH         = int(dbutils.widgets.get("max_depth"))
LEARNING_RATE     = float(dbutils.widgets.get("learning_rate"))
MIN_HISTORY_DAYS  = int(dbutils.widgets.get("min_history_days"))

print(f"Test size        : {TEST_SIZE}")
print(f"n_estimators     : {N_ESTIMATORS}")
print(f"max_depth        : {MAX_DEPTH}")
print(f"learning_rate    : {LEARNING_RATE}")
print(f"min_history_days : {MIN_HISTORY_DAYS}")

# COMMAND ----------
# MAGIC %md ## Load and prepare features
# MAGIC
# MAGIC We need ASINs with enough days of history for the rolling features to be meaningful.

# COMMAND ----------

FEATURE_COLS = [
    "current_price",
    "price_7d_ma",
    "price_7d_volatility",
    "price_momentum",
    "comp_median_price",
    "comp_avg_price",
    "comp_min_price",
    "comp_max_price",
    "comp_count",
    "competitors_below",
    "comp_pressure_score",
]
TARGET_COL = "suggested_price"

raw = spark.table("gold.price_features").toPandas()

# Filter: need target and at least one feature present
raw = raw.dropna(subset=[TARGET_COL, "current_price", "comp_median_price"])

# Filter: ASINs with enough history
asin_counts = raw.groupby("asin")["scrape_date"].count()
valid_asins = asin_counts[asin_counts >= MIN_HISTORY_DAYS].index
df = raw[raw["asin"].isin(valid_asins)].copy()

print(f"Total rows after filtering : {len(df)}")
print(f"Unique ASINs               : {df['asin'].nunique()}")
print(f"Date range                 : {df['scrape_date'].min()} → {df['scrape_date'].max()}")

if len(df) < 10:
    raise ValueError(
        f"Only {len(df)} usable rows — not enough data to train. "
        f"Run the scraper daily for at least {MIN_HISTORY_DAYS} days and re-run this notebook."
    )

# COMMAND ----------
# MAGIC %md ## Feature engineering

# COMMAND ----------

df = df.sort_values(["asin", "scrape_date"])

# Day-of-week seasonality signal (0=Monday … 6=Sunday)
df["day_of_week"] = pd.to_datetime(df["scrape_date"]).dt.dayofweek

# Price ratio to competitor median
df["price_to_median_ratio"] = df["current_price"] / df["comp_median_price"].replace(0, np.nan)

# Impute remaining nulls with column median so XGBoost doesn't drop rows
feature_cols_extended = FEATURE_COLS + ["day_of_week", "price_to_median_ratio"]
for col in feature_cols_extended:
    df[col] = df[col].fillna(df[col].median())

X = df[feature_cols_extended].astype(float)
y = df[TARGET_COL].astype(float)

print(f"Feature matrix shape: {X.shape}")
print(X.describe().T[["mean", "std", "min", "max"]])

# COMMAND ----------
# MAGIC %md ## Train / test split
# MAGIC
# MAGIC We use a time-based split: oldest rows train, newest rows test.
# MAGIC Random splitting would leak future prices into the training set.

# COMMAND ----------

df_sorted = df.sort_values("scrape_date")
split_idx  = int(len(df_sorted) * (1 - TEST_SIZE))

X_train = X.loc[df_sorted.index[:split_idx]]
X_test  = X.loc[df_sorted.index[split_idx:]]
y_train = y.loc[df_sorted.index[:split_idx]]
y_test  = y.loc[df_sorted.index[split_idx:]]

print(f"Train rows: {len(X_train)}  |  Test rows: {len(X_test)}")

# COMMAND ----------
# MAGIC %md ## Train with MLflow tracking

# COMMAND ----------

mlflow.set_experiment("/Shared/pricesense-ai/price_optimization")

with mlflow.start_run(run_name=f"xgboost_d{MAX_DEPTH}_lr{LEARNING_RATE}_n{N_ESTIMATORS}") as run:

    params = {
        "n_estimators":  N_ESTIMATORS,
        "max_depth":     MAX_DEPTH,
        "learning_rate": LEARNING_RATE,
        "subsample":     0.8,
        "colsample_bytree": 0.8,
        "objective":     "reg:squarederror",
        "random_state":  42,
    }
    mlflow.log_params(params)

    model = xgb.XGBRegressor(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    preds     = model.predict(X_test)
    rmse      = float(np.sqrt(mean_squared_error(y_test, preds)))
    mae       = float(mean_absolute_error(y_test, preds))
    mape      = float(np.mean(np.abs((y_test - preds) / y_test.replace(0, np.nan))) * 100)

    mlflow.log_metric("rmse", rmse)
    mlflow.log_metric("mae",  mae)
    mlflow.log_metric("mape", mape)

    print(f"RMSE : {rmse:.4f}")
    print(f"MAE  : {mae:.4f}")
    print(f"MAPE : {mape:.2f}%")

    # Feature importances
    importances = pd.Series(model.feature_importances_, index=feature_cols_extended).sort_values(ascending=False)
    print("\nTop feature importances:")
    print(importances.head(10))
    mlflow.log_dict(importances.to_dict(), "feature_importances.json")

    # Log model with input/output signature for serving
    signature = infer_signature(X_train, preds)
    mlflow.xgboost.log_model(
        model,
        artifact_path="model",
        signature=signature,
        input_example=X_train.head(3),
        registered_model_name="PriceOptimizationModel",
    )

    run_id = run.info.run_id
    print(f"\nMLflow run ID: {run_id}")
    print(f"Model registered as: PriceOptimizationModel")

# COMMAND ----------
# MAGIC %md ## SHAP feature explanations (optional but interview-gold)
# MAGIC
# MAGIC SHAP shows *why* the model made each prediction — not just which features matter
# MAGIC globally, but which pushed a specific price recommendation up or down.

# COMMAND ----------

try:
    import shap
    explainer  = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(X_test)
    shap_df    = pd.DataFrame(shap_vals, columns=feature_cols_extended)
    shap_means = shap_df.abs().mean().sort_values(ascending=False)
    print("Mean |SHAP| values (feature impact ranking):")
    print(shap_means.to_string())
except ImportError:
    print("SHAP not installed — run %pip install shap and re-run this cell for explanations")

# COMMAND ----------
# MAGIC %md ## Promote to Production (run manually after reviewing metrics)
# MAGIC
# MAGIC Uncomment and run this cell when you're satisfied with the RMSE.
# MAGIC Best practice: compare against the current Production model before promoting.

# COMMAND ----------

# from mlflow.tracking import MlflowClient
#
# client = MlflowClient()
#
# # Get the version that was just registered
# versions = client.get_latest_versions("PriceOptimizationModel", stages=["None"])
# new_version = versions[0].version
#
# # Transition to Production (archives the current Production version automatically)
# client.transition_model_version_stage(
#     name="PriceOptimizationModel",
#     version=new_version,
#     stage="Production",
#     archive_existing_versions=True,
# )
# print(f"✓ PriceOptimizationModel v{new_version} → Production")

# COMMAND ----------
# MAGIC %md ## Load model from registry and score (inference example)
# MAGIC
# MAGIC This is what the FastAPI serving endpoint would call.

# COMMAND ----------

# logged_model = "models:/PriceOptimizationModel/Production"
# loaded_model = mlflow.xgboost.load_model(logged_model)
#
# sample = X_test.head(5)
# predicted_prices = loaded_model.predict(sample)
# print(pd.DataFrame({"asin": df_sorted.iloc[-len(X_test):][:5]["asin"].values,
#                     "actual": y_test.head(5).values,
#                     "predicted": predicted_prices}))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC **What you now have:**
# MAGIC - An MLflow experiment at `/Shared/pricesense-ai/price_optimization`
# MAGIC - A registered model `PriceOptimizationModel` with RMSE / MAE metrics
# MAGIC - Feature importances showing which signals drive price recommendations
# MAGIC - A path to Production promotion with one manual step
# MAGIC
# MAGIC **In an interview, show this sequence:**
# MAGIC 1. MLflow UI → Experiments → compare two runs with different hyperparameters
# MAGIC 2. Model Registry → `PriceOptimizationModel` → version history
# MAGIC 3. `GET /api/analysis/{asin}` → `suggested_price` sourced from the model
