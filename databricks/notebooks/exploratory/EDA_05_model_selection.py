# Databricks notebook source
# MAGIC %md
# MAGIC # EDA 05 — Model Selection & Baseline Comparison
# MAGIC
# MAGIC **Purpose:** Justify choosing XGBoost by comparing it against simpler alternatives.
# MAGIC Answers:
# MAGIC - Does the trained model beat a naive baseline (just predict `comp_median_price`)?
# MAGIC - How does XGBoost compare to LinearRegression and RandomForest?
# MAGIC - Are the default hyperparameters (n_estimators=200, max_depth=4, lr=0.05) good?
# MAGIC - Do we have enough data? (learning curves)
# MAGIC - Where does the model fail? (residual analysis)
# MAGIC
# MAGIC **Not scheduled.** Run interactively — not part of any Workflow job.

# COMMAND ----------
# MAGIC %md ## Install dependencies

# COMMAND ----------

# %pip install xgboost scikit-learn shap
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

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import learning_curve

from src.evaluation.metrics import compute_metrics
from src.features.definitions import ALL_FEATURE_COLS, TARGET_COL
from src.models.hyperparams import DEFAULT_PARAMS, SEARCH_SPACE
from src.models.price_optimizer import PriceOptimizer

# COMMAND ----------
# MAGIC %md ## Load and prepare features

# COMMAND ----------

MIN_HISTORY_DAYS = 7
TEST_SIZE        = 0.2

raw = spark.table("gold.price_features").toPandas()
raw = raw.dropna(subset=[TARGET_COL, "current_price", "comp_median_price"])

asin_counts = raw.groupby("asin")["scrape_date"].count()
valid_asins = asin_counts[asin_counts >= MIN_HISTORY_DAYS].index
df = raw[raw["asin"].isin(valid_asins)].copy().sort_values(["asin", "scrape_date"])

df["day_of_week"] = pd.to_datetime(df["scrape_date"]).dt.dayofweek
df["price_to_median_ratio"] = df["current_price"] / df["comp_median_price"].replace(0, np.nan)

for col in ALL_FEATURE_COLS:
    if col in df.columns:
        df[col] = df[col].fillna(df[col].median())

df_sorted   = df.sort_values("scrape_date")
split_idx   = int(len(df_sorted) * (1 - TEST_SIZE))
X           = df_sorted[ALL_FEATURE_COLS].astype(float)
y           = df_sorted[TARGET_COL].astype(float)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

print(f"Train rows : {len(X_train)}  |  Test rows : {len(X_test)}")
print(f"Features   : {ALL_FEATURE_COLS}")

# COMMAND ----------
# MAGIC %md ## Naive baseline
# MAGIC
# MAGIC The simplest possible "model": just predict `comp_median_price` directly.
# MAGIC The production model must beat this to be worth the complexity.

# COMMAND ----------

baseline_preds = df_sorted["comp_median_price"].iloc[split_idx:].fillna(df_sorted["comp_median_price"].median()).values
baseline_metrics = compute_metrics(y_test, baseline_preds)
print("=== Naive baseline (predict comp_median_price) ===")
print(f"RMSE : {baseline_metrics['rmse']:.4f}")
print(f"MAE  : {baseline_metrics['mae']:.4f}")
print(f"MAPE : {baseline_metrics['mape']:.2f}%")

# COMMAND ----------
# MAGIC %md ## Model comparison: XGBoost vs Ridge vs RandomForest

# COMMAND ----------

models = {
    "XGBoost (default)":   PriceOptimizer(DEFAULT_PARAMS),
    "Ridge Regression":    Ridge(alpha=1.0),
    "Random Forest":       RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42),
}

results = [{"model": "Naive baseline (comp_median)", **baseline_metrics}]

for name, model in models.items():
    if hasattr(model, "fit") and not isinstance(model, PriceOptimizer):
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
    else:
        model.fit(X_train, y_train, X_val=X_test, y_val=y_test)
        preds = model.predict(X_test)

    m = compute_metrics(y_test, preds)
    results.append({"model": name, **m})
    print(f"\n--- {name} ---")
    print(f"RMSE : {m['rmse']:.4f}  |  MAE : {m['mae']:.4f}  |  MAPE : {m['mape']:.2f}%")

results_df = pd.DataFrame(results).sort_values("rmse")
print("\n=== Model comparison (sorted by RMSE) ===")
print(results_df.round(4).to_string(index=False))
print("\n→ XGBoost should beat the baseline. If not, investigate data quality first.")

# COMMAND ----------
# MAGIC %md ## Hyperparameter sensitivity: n_estimators and max_depth
# MAGIC
# MAGIC Tests whether DEFAULT_PARAMS are near the optimum or if tuning would help significantly.

# COMMAND ----------

xgb_optimizer = PriceOptimizer(DEFAULT_PARAMS)
xgb_optimizer.fit(X_train, y_train, X_val=X_test, y_val=y_test)
default_preds = xgb_optimizer.predict(X_test)

print("=== n_estimators sensitivity ===")
for n in [50, 100, 200, 300, 500]:
    p = {**DEFAULT_PARAMS, "n_estimators": n}
    m = PriceOptimizer(p).fit(X_train, y_train).predict(X_test)
    metrics = compute_metrics(y_test, m)
    marker = " ← default" if n == DEFAULT_PARAMS["n_estimators"] else ""
    print(f"  n={n:>3}  RMSE={metrics['rmse']:.4f}  MAPE={metrics['mape']:.2f}%{marker}")

print("\n=== max_depth sensitivity ===")
for d in [2, 3, 4, 5, 6, 8]:
    p = {**DEFAULT_PARAMS, "max_depth": d}
    m = PriceOptimizer(p).fit(X_train, y_train).predict(X_test)
    metrics = compute_metrics(y_test, m)
    marker = " ← default" if d == DEFAULT_PARAMS["max_depth"] else ""
    print(f"  depth={d}  RMSE={metrics['rmse']:.4f}  MAPE={metrics['mape']:.2f}%{marker}")

# COMMAND ----------
# MAGIC %md ## Learning curves: how much data do we need?
# MAGIC
# MAGIC If RMSE is still falling at the full training size, we need more data.
# MAGIC If it plateaus early, the model is data-efficient.

# COMMAND ----------

import xgboost as xgb

xgb_model = xgb.XGBRegressor(**DEFAULT_PARAMS)

if len(X_train) >= 5:
    train_sizes = np.linspace(0.2, 1.0, min(5, len(X_train)))
    print("=== Learning curve (train size vs RMSE) ===")
    print(f"{'Train size':>12} {'Train RMSE':>12} {'Test RMSE':>12}")
    for frac in train_sizes:
        n = max(2, int(len(X_train) * frac))
        xgb_model.fit(X_train.iloc[:n], y_train.iloc[:n], verbose=False)
        train_rmse = compute_metrics(y_train.iloc[:n], xgb_model.predict(X_train.iloc[:n]))["rmse"]
        test_rmse  = compute_metrics(y_test, xgb_model.predict(X_test))["rmse"]
        print(f"{n:>12}  {train_rmse:>12.4f}  {test_rmse:>12.4f}")
    print("\n→ Flat test RMSE = data-efficient. Still falling = need more scrape history.")
else:
    print("Not enough training rows for a meaningful learning curve — run more scrapes first.")

# COMMAND ----------
# MAGIC %md ## Residual analysis
# MAGIC
# MAGIC Are errors random, or correlated with price level / date / ASIN?
# MAGIC Systematic patterns = the model is missing an important feature.

# COMMAND ----------

xgb_optimizer.fit(X_train, y_train)
final_preds = xgb_optimizer.predict(X_test)

residual_df = pd.DataFrame({
    "asin":          df_sorted.iloc[split_idx:]["asin"].values,
    "scrape_date":   df_sorted.iloc[split_idx:]["scrape_date"].values,
    "actual":        y_test.values,
    "predicted":     final_preds,
    "residual":      y_test.values - final_preds,
    "abs_residual":  np.abs(y_test.values - final_preds),
    "current_price": df_sorted.iloc[split_idx:]["current_price"].values,
})

print("=== Residual summary ===")
print(residual_df["residual"].describe().round(4).to_string())

print("\nResidual vs price level (is the model worse for expensive items?):")
residual_df["price_bucket"] = pd.qcut(residual_df["current_price"], q=3, labels=["low", "mid", "high"])
print(residual_df.groupby("price_bucket")["abs_residual"].mean().round(4).to_string())

print("\nWorst predictions:")
print(
    residual_df.nlargest(5, "abs_residual")
    [["asin", "scrape_date", "actual", "predicted", "residual"]]
    .round(2)
    .to_string(index=False)
)

# COMMAND ----------
# MAGIC %md ## Feature importances (XGBoost)

# COMMAND ----------

importances = xgb_optimizer.feature_importances(ALL_FEATURE_COLS)
print("=== XGBoost feature importances ===")
print(importances.round(4).to_string())
print("\nTop 3 features drive the most predictions — confirm they make business sense.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Key Findings
# MAGIC
# MAGIC Fill in after running:
# MAGIC - [ ] Does XGBoost beat the naive baseline? By how much?
# MAGIC - [ ] Is XGBoost significantly better than Ridge or RandomForest?
# MAGIC - [ ] Are the default hyperparameters near the optimum?
# MAGIC - [ ] Do learning curves suggest we need more data?
# MAGIC - [ ] Are residuals random or correlated with price level / ASIN?
