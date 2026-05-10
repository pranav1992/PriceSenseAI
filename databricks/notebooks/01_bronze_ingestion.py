# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Bronze Ingestion
# MAGIC
# MAGIC **Layer:** Bronze (raw, append-only)
# MAGIC
# MAGIC **What this does:**
# MAGIC Reads JSON files that `ingestion/jobs/ingest_products.py` dropped into cloud storage
# MAGIC and appends them to `bronze.products` and `bronze.competitors` Delta tables.
# MAGIC
# MAGIC **Key principle — append only:**
# MAGIC Every row written here is kept forever. We never update or delete Bronze rows.
# MAGIC If a scrape produces bad data, we fix it in Silver (next notebook), not here.
# MAGIC This lets us reprocess from the source without re-calling the Oxylabs API.
# MAGIC
# MAGIC **Run:** Daily, scheduled via Databricks Workflow (see `../jobs/bronze_job.yml`)

# COMMAND ----------
# MAGIC %md ## Parameters
# MAGIC
# MAGIC | Parameter | Description | Example |
# MAGIC |-----------|-------------|---------|
# MAGIC | `storage_path` | Root path where ingestion jobs write JSON files | `s3://my-bucket/pricesense` |
# MAGIC | `scrape_date` | Date to ingest (blank = today UTC) | `2026-05-10` |

# COMMAND ----------

import json
from datetime import datetime, timezone

from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# COMMAND ----------

dbutils.widgets.text("storage_path", "", "Cloud Storage Root Path")
dbutils.widgets.text("scrape_date",  "", "Scrape Date (YYYY-MM-DD, blank = today UTC)")

STORAGE_PATH = dbutils.widgets.get("storage_path").rstrip("/")
SCRAPE_DATE  = dbutils.widgets.get("scrape_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

if not STORAGE_PATH:
    raise ValueError(
        "storage_path widget is required. "
        "Set it to the root where ingest_products.py writes JSON files, "
        "e.g. s3://my-bucket/pricesense or abfss://container@account.dfs.core.windows.net/pricesense"
    )

print(f"Storage path : {STORAGE_PATH}")
print(f"Scrape date  : {SCRAPE_DATE}")

# COMMAND ----------
# MAGIC %md ## Schemas

# COMMAND ----------

_product_schema = StructType([
    StructField("asin",             StringType(),        False),
    StructField("title",            StringType(),        True),
    StructField("brand",            StringType(),        True),
    StructField("price",            DoubleType(),        True),
    StructField("currency",         StringType(),        True),
    StructField("stock",            StringType(),        True),
    StructField("rating",           DoubleType(),        True),
    StructField("url",              StringType(),        True),
    StructField("images",           ArrayType(StringType()), True),
    StructField("categories",       ArrayType(StringType()), True),
    StructField("category_path",    ArrayType(StringType()), True),
    StructField("buybox",           StringType(),        True),
    StructField("product_overview", StringType(),        True),
    StructField("amazon_domain",    StringType(),        True),
    StructField("geo_location",     StringType(),        True),
    StructField("scraped_at",       TimestampType(),     False),
])

_competitor_schema = StructType([
    StructField("parent_asin",   StringType(),        False),
    StructField("asin",          StringType(),        False),
    StructField("title",         StringType(),        True),
    StructField("brand",         StringType(),        True),
    StructField("price",         DoubleType(),        True),
    StructField("currency",      StringType(),        True),
    StructField("rating",        DoubleType(),        True),
    StructField("url",           StringType(),        True),
    StructField("images",        ArrayType(StringType()), True),
    StructField("amazon_domain", StringType(),        True),
    StructField("fetched_at",    TimestampType(),     False),
])

# COMMAND ----------
# MAGIC %md ## Ingest Products → `bronze.products`

# COMMAND ----------

products_path = f"{STORAGE_PATH}/products/{SCRAPE_DATE}/"
print(f"Reading products from: {products_path}")

raw_products = (
    spark.read
    .schema(_product_schema)
    .option("multiLine", True)
    .json(products_path)
    .filter(F.col("asin").isNotNull())
    .withColumn("_ingested_at", F.current_timestamp())
)

product_count = raw_products.count()
print(f"Products found: {product_count}")

if product_count == 0:
    print("WARNING: No product files found for this date. Skipping bronze.products write.")
else:
    raw_products.show(5, truncate=True)
    raw_products.write.format("delta").mode("append").saveAsTable("bronze.products")
    print(f"✓ Appended {product_count} rows to bronze.products")

# COMMAND ----------
# MAGIC %md ## Ingest Competitors → `bronze.competitors`

# COMMAND ----------

competitors_path = f"{STORAGE_PATH}/competitors/{SCRAPE_DATE}/"
print(f"Reading competitors from: {competitors_path}")

raw_competitors = (
    spark.read
    .schema(_competitor_schema)
    .option("multiLine", True)
    .json(competitors_path)
    .filter(F.col("asin").isNotNull() & F.col("parent_asin").isNotNull())
    .withColumn("_ingested_at", F.current_timestamp())
)

competitor_count = raw_competitors.count()
print(f"Competitors found: {competitor_count}")

if competitor_count == 0:
    print("WARNING: No competitor files found for this date. Skipping bronze.competitors write.")
else:
    raw_competitors.show(5, truncate=True)
    raw_competitors.write.format("delta").mode("append").saveAsTable("bronze.competitors")
    print(f"✓ Appended {competitor_count} rows to bronze.competitors")

# COMMAND ----------
# MAGIC %md ## Verify: Time Travel
# MAGIC
# MAGIC This is one of Delta Lake's most powerful features.
# MAGIC Run `DESCRIBE HISTORY bronze.products` to see every version of this table —
# MAGIC you can query any past version with `VERSION AS OF` or `TIMESTAMP AS OF`.

# COMMAND ----------

print("=== bronze.products history ===")
spark.sql("DESCRIBE HISTORY bronze.products").select(
    "version", "timestamp", "operation", "operationMetrics"
).show(10, truncate=False)

print("=== bronze.competitors history ===")
spark.sql("DESCRIBE HISTORY bronze.competitors").select(
    "version", "timestamp", "operation", "operationMetrics"
).show(10, truncate=False)

# COMMAND ----------
# MAGIC %md ## Row counts by date
# MAGIC
# MAGIC Useful for spotting missing scrape days at a glance.

# COMMAND ----------

print("=== bronze.products: rows per scrape date ===")
spark.sql("""
  SELECT DATE(scraped_at) AS scrape_date, COUNT(*) AS row_count
  FROM bronze.products
  GROUP BY DATE(scraped_at)
  ORDER BY scrape_date DESC
""").show(20, truncate=False)

print("=== bronze.competitors: rows per fetch date ===")
spark.sql("""
  SELECT DATE(fetched_at) AS fetch_date, COUNT(*) AS row_count, COUNT(DISTINCT parent_asin) AS products_tracked
  FROM bronze.competitors
  GROUP BY DATE(fetched_at)
  ORDER BY fetch_date DESC
""").show(20, truncate=False)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC Next step: run `02_silver_cleaning.py` to deduplicate and normalize this data
# MAGIC into `silver.price_history` and `silver.competitor_map`.
