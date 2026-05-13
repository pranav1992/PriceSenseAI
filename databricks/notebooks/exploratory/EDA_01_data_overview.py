# Databricks notebook source
# MAGIC %md
# MAGIC # EDA 01 — Data Overview & Layer Health
# MAGIC
# MAGIC **Purpose:** Understand the shape, completeness, and coverage of data across all
# MAGIC Medallion layers before any modelling work. Run this first whenever you onboard
# MAGIC to the project or after a period of missed scrapes.
# MAGIC
# MAGIC **Not scheduled.** Run interactively in Databricks — not part of any Workflow job.

# COMMAND ----------
# MAGIC %md ## Bronze Layer

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------
# MAGIC %md ### Row counts and date coverage

# COMMAND ----------

print("=== bronze.products ===")
bp = spark.table("bronze.products")
print(f"Total rows     : {bp.count():,}")
print(f"Unique ASINs   : {bp.select('asin').distinct().count()}")
bp.select(F.min("scraped_at").alias("earliest"), F.max("scraped_at").alias("latest")).show()

print("\n=== bronze.competitors ===")
bc = spark.table("bronze.competitors")
print(f"Total rows          : {bc.count():,}")
print(f"Unique parent ASINs : {bc.select('parent_asin').distinct().count()}")
print(f"Unique comp ASINs   : {bc.select('asin').distinct().count()}")
bc.select(F.min("fetched_at").alias("earliest"), F.max("fetched_at").alias("latest")).show()

# COMMAND ----------
# MAGIC %md ### Daily scrape volume — spot missing days

# COMMAND ----------

print("=== bronze.products: rows per scrape day ===")
spark.sql("""
  SELECT DATE(scraped_at) AS scrape_date, COUNT(*) AS rows, COUNT(DISTINCT asin) AS unique_asins
  FROM bronze.products
  GROUP BY DATE(scraped_at)
  ORDER BY scrape_date DESC
""").show(30, truncate=False)

# COMMAND ----------
# MAGIC %md ### Null rates — bronze.products

# COMMAND ----------

total = bp.count()
null_rates = []
for col_name in bp.columns:
    null_count = bp.filter(F.col(col_name).isNull()).count()
    null_rates.append((col_name, null_count, round(null_count / total * 100, 1)))

import pandas as pd
null_df = pd.DataFrame(null_rates, columns=["column", "null_count", "null_pct"]).sort_values("null_pct", ascending=False)
print("Null rates in bronze.products:")
print(null_df.to_string(index=False))
print("\n⚠ Columns with >10% nulls:")
print(null_df[null_df["null_pct"] > 10].to_string(index=False) or "  None")

# COMMAND ----------
# MAGIC %md ## Silver Layer

# COMMAND ----------
# MAGIC %md ### Price history completeness

# COMMAND ----------

print("=== silver.price_history ===")
sph = spark.table("silver.price_history")
print(f"Total rows   : {sph.count():,}")
print(f"Unique ASINs : {sph.select('asin').distinct().count()}")
sph.select(F.min("scrape_date").alias("earliest"), F.max("scrape_date").alias("latest")).show()

print("\nRows by source:")
sph.groupBy("source").count().show()

# COMMAND ----------
# MAGIC %md ### Stock status distribution

# COMMAND ----------

print("=== silver.price_history: stock status breakdown ===")
spark.sql("""
  SELECT stock, COUNT(*) AS rows, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
  FROM silver.price_history
  WHERE source = 'product'
  GROUP BY stock
  ORDER BY rows DESC
""").show()

# COMMAND ----------
# MAGIC %md ### Competitor map coverage

# COMMAND ----------

print("=== silver.competitor_map ===")
scm = spark.table("silver.competitor_map")
print(f"Total rows          : {scm.count():,}")
print(f"Unique parent ASINs : {scm.select('parent_asin').distinct().count()}")
print(f"Date range          : ", end="")
scm.select(F.min("scrape_date"), F.max("scrape_date")).show()

print("Competitors per parent ASIN (avg / min / max):")
scm.groupBy("parent_asin").agg(
    F.avg("price_rank").alias("avg_competitors"),
    F.min("price_rank").alias("min_rank"),
    F.max("price_rank").alias("max_rank"),
).show()

# COMMAND ----------
# MAGIC %md ## Gold Layer

# COMMAND ----------
# MAGIC %md ### Feature completeness

# COMMAND ----------

print("=== gold.price_features ===")
gpf = spark.table("gold.price_features")
print(f"Total rows   : {gpf.count():,}")
print(f"Unique ASINs : {gpf.select('asin').distinct().count()}")
gpf.select(F.min("scrape_date").alias("earliest"), F.max("scrape_date").alias("latest")).show()

# COMMAND ----------

total_gold = gpf.count()
feature_cols = [
    "current_price", "price_7d_ma", "price_7d_volatility", "price_momentum",
    "comp_median_price", "comp_avg_price", "comp_min_price", "comp_max_price",
    "comp_count", "competitors_below", "comp_pressure_score", "suggested_price",
]
null_rates_gold = []
for col_name in feature_cols:
    nc = gpf.filter(F.col(col_name).isNull()).count()
    null_rates_gold.append((col_name, nc, round(nc / total_gold * 100, 1)))

gold_null_df = pd.DataFrame(null_rates_gold, columns=["feature", "null_count", "null_pct"]).sort_values("null_pct", ascending=False)
print("Null rates in gold.price_features (feature columns):")
print(gold_null_df.to_string(index=False))

# COMMAND ----------
# MAGIC %md ### ASINs with sufficient history for training

# COMMAND ----------

asin_history = (
    gpf
    .groupBy("asin")
    .agg(F.count("*").alias("days_of_history"))
    .orderBy("days_of_history", ascending=False)
)
asin_history.show()

min_days = 7
qualified = asin_history.filter(F.col("days_of_history") >= min_days).count()
print(f"\nASINs with ≥{min_days} days of history (model-ready): {qualified}")

# COMMAND ----------
# MAGIC %md ### price_position distribution

# COMMAND ----------

print("=== gold.price_features: price_position breakdown ===")
spark.sql("""
  SELECT price_position, COUNT(*) AS rows, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
  FROM gold.price_features
  GROUP BY price_position
  ORDER BY rows DESC
""").show()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC Run this notebook at the start of any modelling session to confirm:
# MAGIC - No recent scrape days are missing
# MAGIC - Null rates are acceptable in the feature columns
# MAGIC - Enough ASINs have ≥7 days of history to train a meaningful model
