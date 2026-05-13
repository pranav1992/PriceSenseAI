# Databricks notebook source
# MAGIC %md
# MAGIC # EDA 02 — Price Distribution & Time-Series Analysis
# MAGIC
# MAGIC **Purpose:** Understand how prices behave over time — distributions, trends,
# MAGIC volatility, and day-of-week seasonality. Answers:
# MAGIC - Is the 7-day rolling window meaningful? (do prices change at weekly cadence?)
# MAGIC - Does `day_of_week` add signal? (do prices differ Mon vs Fri?)
# MAGIC - How volatile are prices? (does the model need to handle large swings?)
# MAGIC
# MAGIC **Not scheduled.** Run interactively — not part of any Workflow job.

# COMMAND ----------

import pandas as pd
import numpy as np
from pyspark.sql import functions as F

# COMMAND ----------
# MAGIC %md ## Load price history

# COMMAND ----------

own_prices = (
    spark.table("silver.price_history")
    .filter(F.col("source") == "product")
    .filter(F.col("price").isNotNull())
    .orderBy("asin", "scrape_date")
    .toPandas()
)

own_prices["scrape_date"] = pd.to_datetime(own_prices["scrape_date"])
own_prices["day_of_week"] = own_prices["scrape_date"].dt.dayofweek
own_prices["day_name"] = own_prices["scrape_date"].dt.day_name()

print(f"Rows: {len(own_prices)}  |  ASINs: {own_prices['asin'].nunique()}")
print(own_prices[["asin", "scrape_date", "price", "rating", "stock"]].head(10).to_string(index=False))

# COMMAND ----------
# MAGIC %md ## Price distribution

# COMMAND ----------

print("=== Price distribution (own products) ===")
print(own_prices["price"].describe().round(2).to_string())

print("\nPercentiles:")
for p in [5, 25, 50, 75, 90, 95, 99]:
    print(f"  p{p:>2}: {np.percentile(own_prices['price'].dropna(), p):.2f}")

# COMMAND ----------
# MAGIC %md ## Price over time per ASIN

# COMMAND ----------

for asin, grp in own_prices.groupby("asin"):
    grp = grp.sort_values("scrape_date")
    print(f"\n--- ASIN: {asin} ({len(grp)} days) ---")
    print(f"  Price range : {grp['price'].min():.2f} → {grp['price'].max():.2f}")
    print(f"  Std dev     : {grp['price'].std():.4f}")
    print(f"  CV (std/mean): {grp['price'].std() / grp['price'].mean():.4f}")
    print(grp[["scrape_date", "price"]].to_string(index=False))

# COMMAND ----------
# MAGIC %md ## Rolling 7d MA vs raw price
# MAGIC
# MAGIC This validates the choice of 7-day window in `03_gold_features.py`.
# MAGIC A window that's too short follows noise; too long misses real price changes.

# COMMAND ----------

gold = spark.table("gold.price_features").orderBy("asin", "scrape_date").toPandas()
gold["scrape_date"] = pd.to_datetime(gold["scrape_date"])

for asin, grp in gold.groupby("asin"):
    grp = grp.sort_values("scrape_date")
    print(f"\n--- ASIN: {asin} ---")
    print(f"{'Date':<14} {'Raw':>8} {'7d MA':>8} {'Diff':>8}")
    for _, row in grp.iterrows():
        raw  = row["current_price"]
        ma   = row["price_7d_ma"]
        diff = raw - ma if pd.notna(ma) else float("nan")
        print(f"{str(row['scrape_date'].date()):<14} {raw:>8.2f} {ma:>8.2f} {diff:>+8.2f}")

# COMMAND ----------
# MAGIC %md ## Day-of-week price patterns
# MAGIC
# MAGIC If prices are consistently lower on certain days, `day_of_week` is a useful feature.
# MAGIC If there's no pattern, it adds noise.

# COMMAND ----------

day_stats = (
    own_prices
    .groupby(["day_of_week", "day_name"])["price"]
    .agg(["mean", "median", "std", "count"])
    .reset_index()
    .sort_values("day_of_week")
)
day_stats.columns = ["dow", "day", "mean_price", "median_price", "std", "count"]
print("=== Price by day of week ===")
print(day_stats.round(4).to_string(index=False))

overall_mean = own_prices["price"].mean()
day_stats["vs_avg_pct"] = (day_stats["mean_price"] - overall_mean) / overall_mean * 100
print("\nDay vs overall average (%):")
print(day_stats[["day", "vs_avg_pct"]].round(2).to_string(index=False))
print(f"\nMax spread across days: {day_stats['vs_avg_pct'].max() - day_stats['vs_avg_pct'].min():.2f}%")
print("→ If spread < 1%, day_of_week adds little signal.")

# COMMAND ----------
# MAGIC %md ## Price volatility analysis
# MAGIC
# MAGIC `price_7d_volatility` (std dev) drives the model's uncertainty estimate.
# MAGIC Highly volatile products may need more frequent retraining.

# COMMAND ----------

if "price_7d_volatility" in gold.columns:
    vol_stats = gold.dropna(subset=["price_7d_volatility"])
    print("=== price_7d_volatility distribution ===")
    print(vol_stats["price_7d_volatility"].describe().round(4).to_string())
    print("\nASINs with highest volatility:")
    print(
        vol_stats.groupby("asin")["price_7d_volatility"].mean()
        .sort_values(ascending=False)
        .round(4)
        .to_string()
    )

# COMMAND ----------
# MAGIC %md ## Price momentum distribution
# MAGIC
# MAGIC `price_momentum` = (price_today − price_7d_ago) / price_7d_ago.
# MAGIC Positive = prices rising; negative = falling.
# MAGIC Most rows should cluster near 0 for stable products.

# COMMAND ----------

if "price_momentum" in gold.columns:
    mom = gold["price_momentum"].dropna()
    print("=== price_momentum distribution ===")
    print(mom.describe().round(4).to_string())
    print(f"\nFraction with >5% change  : {(mom.abs() > 0.05).mean():.1%}")
    print(f"Fraction with >10% change : {(mom.abs() > 0.10).mean():.1%}")
    print(f"Fraction with >20% change : {(mom.abs() > 0.20).mean():.1%}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Key Findings
# MAGIC
# MAGIC Fill in after running:
# MAGIC - [ ] Is the 7-day window appropriate for the price cadence observed?
# MAGIC - [ ] Does day_of_week show a consistent pattern (>1% spread)?
# MAGIC - [ ] Are prices mostly stable (low CV) or highly volatile?
# MAGIC - [ ] Does price_momentum cluster near 0 or show frequent large swings?
