# Databricks notebook source
# MAGIC %md
# MAGIC # EDA 03 — Competitor Landscape & Market Positioning
# MAGIC
# MAGIC **Purpose:** Understand the competitive environment that drives the pricing model.
# MAGIC Answers:
# MAGIC - How many competitors does each product face?
# MAGIC - How spread is competitor pricing (is the median a robust anchor)?
# MAGIC - Is rating correlated with price? (validates the rating premium feature)
# MAGIC - Does the cheapest competitor stay cheapest across days? (price rank stability)
# MAGIC - Where do our products sit relative to the market?
# MAGIC
# MAGIC **Not scheduled.** Run interactively — not part of any Workflow job.

# COMMAND ----------

import pandas as pd
import numpy as np
from pyspark.sql import functions as F

# COMMAND ----------
# MAGIC %md ## Load competitor data

# COMMAND ----------

comp_map = spark.table("silver.competitor_map").toPandas()
comp_map["scrape_date"] = pd.to_datetime(comp_map["scrape_date"])

gold = spark.table("gold.price_features").toPandas()
gold["scrape_date"] = pd.to_datetime(gold["scrape_date"])

print(f"Competitor map rows : {len(comp_map):,}")
print(f"Unique parent ASINs : {comp_map['parent_asin'].nunique()}")
print(f"Unique comp ASINs   : {comp_map['asin'].nunique()}")
print(comp_map.head(5).to_string(index=False))

# COMMAND ----------
# MAGIC %md ## Competitor count per product
# MAGIC
# MAGIC How many competitors does each product face on a typical day?
# MAGIC Low counts → `comp_median_price` may be noisy.

# COMMAND ----------

comp_count_daily = (
    comp_map.groupby(["parent_asin", "scrape_date"])["asin"]
    .count()
    .reset_index()
    .rename(columns={"asin": "comp_count"})
)

print("=== Competitor count per product per day ===")
print(comp_count_daily.groupby("parent_asin")["comp_count"].describe().round(1).to_string())

print("\nOverall distribution:")
print(comp_count_daily["comp_count"].describe().round(1).to_string())

# COMMAND ----------
# MAGIC %md ## Competitor price spread
# MAGIC
# MAGIC How wide is the price range among competitors?
# MAGIC A wide spread means median is more robust than mean.

# COMMAND ----------

price_spread = (
    comp_map.groupby(["parent_asin", "scrape_date"])["price"]
    .agg(["min", "max", "median", "std"])
    .reset_index()
)
price_spread["spread_pct"] = (price_spread["max"] - price_spread["min"]) / price_spread["median"] * 100

print("=== Competitor price spread (% of median) ===")
print(price_spread.groupby("parent_asin")["spread_pct"].describe().round(1).to_string())

print("\nOverall:")
print(price_spread["spread_pct"].describe().round(1).to_string())
print(f"\nMedian vs Mean difference (median is more robust when spread is wide):")
price_spread["median_vs_mean"] = abs(price_spread["median"] - price_spread["std"]) / price_spread["median"] * 100
print(price_spread["median_vs_mean"].describe().round(2).to_string())

# COMMAND ----------
# MAGIC %md ## Competitor price_diff_pct distribution
# MAGIC
# MAGIC `price_diff_pct` = (competitor_price − own_price) / own_price × 100.
# MAGIC Positive = competitor is more expensive than us.

# COMMAND ----------

print("=== price_diff_pct: how competitors price relative to us ===")
print(comp_map["price_diff_pct"].dropna().describe().round(2).to_string())

bins = [-100, -20, -10, -5, 0, 5, 10, 20, 100]
labels = ["<-20%", "-20→-10%", "-10→-5%", "-5→0%", "0→5%", "5→10%", "10→20%", ">20%"]
comp_map["diff_bucket"] = pd.cut(comp_map["price_diff_pct"].dropna(), bins=bins, labels=labels)
bucket_counts = comp_map["diff_bucket"].value_counts().sort_index()
print("\nPrice diff distribution:")
for bucket, count in bucket_counts.items():
    pct = count / bucket_counts.sum() * 100
    print(f"  {bucket:<12} : {count:>5}  ({pct:.1f}%)")

# COMMAND ----------
# MAGIC %md ## Rating vs Price — does higher-rated = higher-priced?
# MAGIC
# MAGIC This validates the rating premium feature:
# MAGIC `suggested_price += 3%` if own rating exceeds competitors by >0.3 stars.

# COMMAND ----------

comp_with_rating = comp_map.dropna(subset=["rating", "price"])

print("=== Correlation: competitor rating vs price ===")
corr = comp_with_rating[["rating", "price"]].corr()
print(corr.round(3).to_string())

print("\nAverage price by rating bucket:")
comp_with_rating["rating_bucket"] = pd.cut(
    comp_with_rating["rating"],
    bins=[0, 3.0, 3.5, 4.0, 4.5, 5.0],
    labels=["<3.0", "3.0-3.5", "3.5-4.0", "4.0-4.5", "4.5-5.0"]
)
print(
    comp_with_rating.groupby("rating_bucket")["price"]
    .agg(["mean", "median", "count"])
    .round(2)
    .to_string()
)
print("\n→ If higher-rated competitors charge more, the rating premium feature is justified.")

# COMMAND ----------
# MAGIC %md ## Price rank stability
# MAGIC
# MAGIC Does the cheapest competitor stay cheapest from day to day?
# MAGIC High instability → `price_rank` is noisy and may not be a useful feature.

# COMMAND ----------

rank_stability = (
    comp_map.groupby(["parent_asin", "asin"])["price_rank"]
    .agg(["mean", "std", "count"])
    .reset_index()
    .rename(columns={"mean": "avg_rank", "std": "rank_std", "count": "days_seen"})
    .sort_values("avg_rank")
)

print("=== Competitor price rank stability (std dev over time) ===")
print(rank_stability.round(2).to_string(index=False))
print(f"\nAvg rank std dev: {rank_stability['rank_std'].mean():.2f}")
print("→ Low std (< 1) = stable ranking. High std = competitors frequently swap positions.")

# COMMAND ----------
# MAGIC %md ## Our products' market position
# MAGIC
# MAGIC `comp_pressure_score` = fraction of competitors cheaper than us.
# MAGIC 0 = we are cheapest; 1 = all competitors are cheaper than us.

# COMMAND ----------

if "comp_pressure_score" in gold.columns:
    pressure = gold["comp_pressure_score"].dropna()
    print("=== comp_pressure_score distribution (own products) ===")
    print(pressure.describe().round(3).to_string())
    print(f"\nAbove market (pressure > 0.7): {(pressure > 0.7).mean():.1%}")
    print(f"At market    (0.3–0.7)       : {((pressure >= 0.3) & (pressure <= 0.7)).mean():.1%}")
    print(f"Below market (pressure < 0.3): {(pressure < 0.3).mean():.1%}")

print("\n=== price_position breakdown ===")
spark.sql("""
  SELECT price_position, COUNT(*) AS rows, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
  FROM gold.price_features
  GROUP BY price_position
  ORDER BY rows DESC
""").show()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Key Findings
# MAGIC
# MAGIC Fill in after running:
# MAGIC - [ ] Do products face enough competitors for `comp_median_price` to be stable?
# MAGIC - [ ] Is there a meaningful rating-price correlation? (justifies rating premium)
# MAGIC - [ ] Is price rank stable across days? (justifies using it as a feature)
# MAGIC - [ ] Are our products mostly above, at, or below market?
