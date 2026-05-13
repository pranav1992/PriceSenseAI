# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — Batch Scoring
# MAGIC
# MAGIC **What this does:**
# MAGIC Loads the Production `PriceOptimizationModel` from the MLflow Model Registry,
# MAGIC scores today's rows from `gold.price_features`, and writes the predictions to
# MAGIC `gold.price_predictions` — one row per `(asin, scrape_date)`.
# MAGIC
# MAGIC **Output table `gold.price_predictions`:**
# MAGIC | Column | Description |
# MAGIC |--------|-------------|
# MAGIC | `asin` | Product identifier |
# MAGIC | `scrape_date` | Feature snapshot date |
# MAGIC | `predicted_price` | Model's suggested price |
# MAGIC | `current_price` | Actual price on that day |
# MAGIC | `price_diff_pct` | % difference (predicted vs current) |
# MAGIC | `model_version` | Registry version used for this score |
# MAGIC | `scored_at` | Timestamp of this scoring run |
# MAGIC
# MAGIC **Run:** Daily (03:00 UTC) after `gold_features` task completes.

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
import mlflow.xgboost
import numpy as np
import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, TimestampType

from src.features.definitions import ALL_FEATURE_COLS
from src.features.validation import check_minimum_rows
from src.utils.mlflow_utils import MODEL_NAME, get_latest_model_version

# COMMAND ----------
# MAGIC %md ## Parameters

# COMMAND ----------

dbutils.widgets.text("scrape_date", "", "Scrape Date (YYYY-MM-DD, blank = today UTC)")
SCRAPE_DATE = dbutils.widgets.get("scrape_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

print(f"Scoring date : {SCRAPE_DATE}")

# COMMAND ----------
# MAGIC %md ## Load Production model

# COMMAND ----------

production = get_latest_model_version(stage="Production")
model_version = production.version
model_uri = f"models:/{MODEL_NAME}/Production"

model = mlflow.xgboost.load_model(model_uri)
print(f"Loaded {MODEL_NAME} v{model_version} from Production")

# COMMAND ----------
# MAGIC %md ## Load and prepare today's features

# COMMAND ----------

raw = (
    spark.table("gold.price_features")
    .filter(F.col("scrape_date") == F.lit(SCRAPE_DATE))
    .toPandas()
)

check_minimum_rows(raw, 1, context=f"for scrape_date={SCRAPE_DATE}")

raw["day_of_week"] = pd.to_datetime(raw["scrape_date"]).dt.dayofweek
raw["price_to_median_ratio"] = raw["current_price"] / raw["comp_median_price"].replace(0, np.nan)

for col in ALL_FEATURE_COLS:
    if col in raw.columns:
        raw[col] = raw[col].fillna(raw[col].median())

X = raw[ALL_FEATURE_COLS].astype(float)
print(f"Rows to score : {len(X)}")

# COMMAND ----------
# MAGIC %md ## Score

# COMMAND ----------

raw["predicted_price"] = model.predict(X)
raw["price_diff_pct"] = (
    (raw["predicted_price"] - raw["current_price"]) / raw["current_price"].replace(0, np.nan) * 100
)
raw["model_version"] = str(model_version)
raw["scored_at"] = datetime.now(timezone.utc)

predictions_pd = raw[
    ["asin", "scrape_date", "predicted_price", "current_price", "price_diff_pct", "model_version", "scored_at"]
].copy()

print(predictions_pd.to_string(index=False))

# COMMAND ----------
# MAGIC %md ## Write to gold.price_predictions

# COMMAND ----------

predictions_df = spark.createDataFrame(predictions_pd)

predictions_df.createOrReplaceTempView("_predictions_staging")

spark.sql("""
MERGE INTO gold.price_predictions AS target
USING _predictions_staging AS source
  ON  target.asin        = source.asin
  AND target.scrape_date = source.scrape_date
WHEN MATCHED THEN UPDATE SET
  target.predicted_price = source.predicted_price,
  target.current_price   = source.current_price,
  target.price_diff_pct  = source.price_diff_pct,
  target.model_version   = source.model_version,
  target.scored_at       = source.scored_at
WHEN NOT MATCHED THEN INSERT (
  asin, scrape_date, predicted_price, current_price, price_diff_pct, model_version, scored_at
) VALUES (
  source.asin, source.scrape_date, source.predicted_price, source.current_price,
  source.price_diff_pct, source.model_version, source.scored_at
)
""")

print(f"✓ Scored {len(predictions_pd)} rows → gold.price_predictions")

# COMMAND ----------
# MAGIC %md ## Verify

# COMMAND ----------

spark.sql(f"""
  SELECT asin, scrape_date,
         ROUND(current_price, 2) AS current,
         ROUND(predicted_price, 2) AS predicted,
         ROUND(price_diff_pct, 2) AS diff_pct,
         model_version
  FROM gold.price_predictions
  WHERE scrape_date = '{SCRAPE_DATE}'
  ORDER BY asin
""").show(truncate=False)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC Next step: run `08_data_drift.py` to check for input feature distribution changes.
