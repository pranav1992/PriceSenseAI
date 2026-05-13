# Databricks notebook source
# MAGIC %md
# MAGIC # EDA 04 — Feature Engineering Sensitivity Analysis
# MAGIC
# MAGIC **Purpose:** Justify (or challenge) the hardcoded constants in the production
# MAGIC feature pipeline by testing alternatives empirically. Answers:
# MAGIC - Is 7 days the right rolling window, or is 3d / 14d better?
# MAGIC - Is ±5% the right price position band?
# MAGIC - Is 0.3 stars the right rating premium threshold?
# MAGIC - Are features multicollinear? (do we need all of them?)
# MAGIC - How does the target `suggested_price` distribute relative to `current_price`?
# MAGIC
# MAGIC **Not scheduled.** Run interactively — not part of any Workflow job.

# COMMAND ----------

import sys
import os

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
from pyspark.sql import Window, functions as F
from pyspark.sql.types import DoubleType

from src.features.definitions import (
    FEATURE_COLS,
    PRICE_POSITION_BAND,
    RATING_PREMIUM_PCT,
    RATING_PREMIUM_THRESHOLD,
    ROLLING_WINDOW_DAYS,
    TARGET_COL,
)

# COMMAND ----------
# MAGIC %md ## Load data

# COMMAND ----------

gold = spark.table("gold.price_features").toPandas()
gold["scrape_date"] = pd.to_datetime(gold["scrape_date"])
gold = gold.sort_values(["asin", "scrape_date"]).reset_index(drop=True)

silver = (
    spark.table("silver.price_history")
    .filter(F.col("source") == "product")
    .filter(F.col("price").isNotNull())
    .orderBy("asin", "scrape_date")
    .toPandas()
)
silver["scrape_date"] = pd.to_datetime(silver["scrape_date"])

print(f"Gold rows   : {len(gold)}")
print(f"Silver rows : {len(silver)}")

# COMMAND ----------
# MAGIC %md ## Rolling window sensitivity: 3d vs 7d vs 14d
# MAGIC
# MAGIC Production uses `ROLLING_WINDOW_DAYS = 7`. Compare moving averages and volatility
# MAGIC across three window sizes to see which tracks price changes most faithfully.

# COMMAND ----------

for window_days in [3, 7, 14]:
    silver[f"ma_{window_days}d"] = (
        silver.groupby("asin")["price"]
        .transform(lambda x: x.rolling(window=window_days, min_periods=1).mean())
    )
    silver[f"vol_{window_days}d"] = (
        silver.groupby("asin")["price"]
        .transform(lambda x: x.rolling(window=window_days, min_periods=1).std())
    )

print(f"Production window : {ROLLING_WINDOW_DAYS} days")
print("\nCorrelation of rolling MAs with raw price:")
for w in [3, 7, 14]:
    corr = silver["price"].corr(silver[f"ma_{w}d"])
    print(f"  {w}d MA vs price : {corr:.4f}")

print("\nRolling MA comparison (last 3 rows per ASIN):")
for asin, grp in silver.groupby("asin"):
    cols = ["scrape_date", "price", "ma_3d", "ma_7d", "ma_14d", "vol_3d", "vol_7d", "vol_14d"]
    print(f"\n--- {asin} ---")
    print(grp[cols].tail(5).round(4).to_string(index=False))

# COMMAND ----------
# MAGIC %md ## Price position band sensitivity: ±3% vs ±5% vs ±10%
# MAGIC
# MAGIC Production uses `PRICE_POSITION_BAND = 0.05`. A wider band means fewer products
# MAGIC are labelled above/below market; a tighter band is more sensitive to small diffs.

# COMMAND ----------

gold_with_comp = gold.dropna(subset=["current_price", "comp_median_price"])

print(f"Production band : ±{PRICE_POSITION_BAND * 100:.0f}%")
print()
for band in [0.03, 0.05, 0.10]:
    above = (gold_with_comp["current_price"] > gold_with_comp["comp_median_price"] * (1 + band)).mean()
    below = (gold_with_comp["current_price"] < gold_with_comp["comp_median_price"] * (1 - band)).mean()
    at    = 1 - above - below
    print(f"Band ±{band*100:.0f}%  →  above: {above:.1%}  at: {at:.1%}  below: {below:.1%}")

print("\n→ Tighter band is more sensitive; wider band reduces noise from small fluctuations.")

# COMMAND ----------
# MAGIC %md ## Rating premium threshold sensitivity
# MAGIC
# MAGIC Production: add 3% to suggested price if own rating − comp avg rating > 0.3.
# MAGIC Test different threshold values to see how many products qualify.

# COMMAND ----------

comp_map = spark.table("silver.competitor_map").toPandas()
own_ratings = (
    spark.table("silver.price_history")
    .filter(F.col("source") == "product")
    .filter(F.col("rating").isNotNull())
    .groupBy("asin")
    .agg(F.avg("rating").alias("own_avg_rating"))
    .toPandas()
)

comp_avg_rating = (
    comp_map.groupby("parent_asin")["rating"]
    .mean()
    .reset_index()
    .rename(columns={"parent_asin": "asin", "rating": "comp_avg_rating"})
)

rating_df = own_ratings.merge(comp_avg_rating, on="asin")
rating_df["rating_diff"] = rating_df["own_avg_rating"] - rating_df["comp_avg_rating"]

print(f"Production threshold : {RATING_PREMIUM_THRESHOLD} stars → {RATING_PREMIUM_PCT*100:.0f}% premium")
print(f"\nRating diff distribution:")
print(rating_df["rating_diff"].describe().round(3).to_string())

print("\nFraction of products qualifying for premium at each threshold:")
for thresh in [0.1, 0.2, 0.3, 0.5, 1.0]:
    pct = (rating_df["rating_diff"] > thresh).mean()
    print(f"  threshold {thresh:.1f} stars : {pct:.1%} of products get premium")

# COMMAND ----------
# MAGIC %md ## Feature correlation matrix
# MAGIC
# MAGIC Identifies multicollinear features that may not both be needed.
# MAGIC Strong correlation (|r| > 0.9) between two features suggests one can be dropped.

# COMMAND ----------

numeric_features = [c for c in FEATURE_COLS if c in gold.columns]
feat_df = gold[numeric_features].dropna()

corr_matrix = feat_df.corr().round(3)
print("=== Feature correlation matrix ===")
print(corr_matrix.to_string())

print("\nHighly correlated pairs (|r| > 0.8):")
found = False
for i in range(len(corr_matrix.columns)):
    for j in range(i + 1, len(corr_matrix.columns)):
        r = corr_matrix.iloc[i, j]
        if abs(r) > 0.8:
            print(f"  {corr_matrix.columns[i]:30s} ↔  {corr_matrix.columns[j]:30s}  r = {r:.3f}")
            found = True
if not found:
    print("  None found above threshold.")

# COMMAND ----------
# MAGIC %md ## Target distribution: suggested_price vs current_price
# MAGIC
# MAGIC How often does the model suggest raising vs lowering the price?
# MAGIC A skewed distribution means the model has a consistent directional bias.

# COMMAND ----------

valid = gold.dropna(subset=["suggested_price", "current_price"])
valid["price_delta"] = valid["suggested_price"] - valid["current_price"]
valid["delta_pct"] = valid["price_delta"] / valid["current_price"] * 100

print("=== suggested_price − current_price ===")
print(valid["price_delta"].describe().round(4).to_string())

print("\n=== % delta ===")
print(valid["delta_pct"].describe().round(2).to_string())

print(f"\nSuggest price increase (>1%)  : {(valid['delta_pct'] >  1).mean():.1%}")
print(f"Suggest no change (±1%)       : {(valid['delta_pct'].abs() <= 1).mean():.1%}")
print(f"Suggest price decrease (<-1%) : {(valid['delta_pct'] < -1).mean():.1%}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Key Findings
# MAGIC
# MAGIC Fill in after running:
# MAGIC - [ ] Which rolling window (3d / 7d / 14d) best tracks price changes for your ASINs?
# MAGIC - [ ] Is ±5% a meaningful band, or should it be tighter/wider?
# MAGIC - [ ] How many products qualify for the rating premium? Is 0.3 stars too strict/lenient?
# MAGIC - [ ] Are `comp_avg_price` and `comp_median_price` highly correlated? (if so, drop one)
# MAGIC - [ ] Does the model systematically suggest raising or lowering prices?
