# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Feature Store Registration
# MAGIC
# MAGIC **What this does:**
# MAGIC Registers `gold.price_features` as a Databricks Feature Store table so that training
# MAGIC and serving notebooks can retrieve features via point-in-time correct lookups.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - Databricks Feature Store is enabled on this workspace (Premium tier or above).
# MAGIC - `gold.price_features` has been populated by `03_gold_features.py`.
# MAGIC
# MAGIC **Run:** Once to register, then re-run whenever the feature schema changes.

# COMMAND ----------
# MAGIC %md ## Parameters

# COMMAND ----------

import sys
from datetime import datetime, timezone

# Auto-detect databricks/ root for src imports when running in Repos
try:
    _nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    _parts = _nb.split("/")
    _dbt_idx = next(i for i, p in enumerate(_parts) if p == "databricks")
    _root = "/".join(_parts[: _dbt_idx + 1])
    if _root not in sys.path:
        sys.path.insert(0, _root)
except Exception:
    pass

from src.features.definitions import ALL_FEATURE_COLS, TARGET_COL

# COMMAND ----------

dbutils.widgets.text("scrape_date", "", "Scrape Date (YYYY-MM-DD, blank = today UTC)")
SCRAPE_DATE = dbutils.widgets.get("scrape_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

print(f"Scrape date : {SCRAPE_DATE}")
print(f"Features    : {ALL_FEATURE_COLS}")
print(f"Target      : {TARGET_COL}")

# COMMAND ----------
# MAGIC %md ## Register with Databricks Feature Store
# MAGIC
# MAGIC The Feature Store wraps `gold.price_features` and tracks which model versions
# MAGIC consumed which feature snapshot — critical for reproducibility audits.

# COMMAND ----------

try:
    from databricks.feature_store import FeatureStoreClient

    fs = FeatureStoreClient()

    fs.register_table(
        delta_table="gold.price_features",
        primary_keys=["asin", "scrape_date"],
        description=(
            "ML-ready price features per (asin, scrape_date): rolling time-series, "
            "competitive aggregates, suggested price, and market position."
        ),
    )
    print("✓ gold.price_features registered in Feature Store")

except ImportError:
    print(
        "Databricks Feature Store SDK not available on this cluster. "
        "Install databricks-feature-store or use a Databricks ML Runtime cluster."
    )
except Exception as e:
    print(f"Feature Store registration skipped: {e}")
    print("Proceeding with direct Delta table access (no FS point-in-time lookups).")

# COMMAND ----------
# MAGIC %md ## Validate feature table

# COMMAND ----------

features_df = spark.table("gold.price_features")

print(f"Total rows      : {features_df.count()}")
print(f"Unique ASINs    : {features_df.select('asin').distinct().count()}")
print(f"Date range      : ", end="")
features_df.selectExpr("min(scrape_date)", "max(scrape_date)").show(truncate=False)

print(f"\nSchema:")
features_df.printSchema()

print(f"\nSample rows (latest date):")
spark.sql(f"""
  SELECT asin, scrape_date, current_price, suggested_price, price_position,
         comp_count, ROUND(comp_pressure_score, 3) AS pressure
  FROM gold.price_features
  ORDER BY scrape_date DESC, asin
  LIMIT 10
""").show(truncate=False)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC Next step: run `05_train_price_model.py` to train XGBoost on these features.
