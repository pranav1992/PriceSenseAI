# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Silver Cleaning
# MAGIC
# MAGIC **Layer:** Silver (cleaned, deduplicated)
# MAGIC
# MAGIC **What this does:**
# MAGIC Reads today's raw rows from `bronze.products` and `bronze.competitors`, normalises
# MAGIC them, and upserts into `silver.price_history` and `silver.competitor_map` using
# MAGIC `MERGE INTO` — so running this notebook twice on the same data is safe.
# MAGIC
# MAGIC **Key principle — idempotency:**
# MAGIC `MERGE INTO` matches on the natural key `(asin, scrape_date, source)`.
# MAGIC Re-running with the same bronze data produces no change in Silver row counts.
# MAGIC This means the job can be safely retried after failures.
# MAGIC
# MAGIC **Run:** Daily after bronze ingestion (see `../databricks.yml`)

# COMMAND ----------
# MAGIC %md ## Parameters
# MAGIC
# MAGIC | Parameter | Description | Example |
# MAGIC |-----------|-------------|---------|
# MAGIC | `scrape_date` | Date to clean (blank = today UTC) | `2026-05-10` |

# COMMAND ----------

from datetime import datetime, timezone

from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType

# COMMAND ----------

dbutils.widgets.text("scrape_date", "", "Scrape Date (YYYY-MM-DD, blank = today UTC)")
SCRAPE_DATE = dbutils.widgets.get("scrape_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

print(f"Scrape date: {SCRAPE_DATE}")

# COMMAND ----------
# MAGIC %md ## Stock normalisation helper
# MAGIC
# MAGIC Oxylabs returns free-text stock strings. We normalise them to four canonical values
# MAGIC so downstream queries can use `WHERE stock = 'out_of_stock'` reliably.

# COMMAND ----------

_STOCK_MAP = {
    "in stock":         "in_stock",
    "in_stock":         "in_stock",
    "available":        "in_stock",
    "limited":          "low_stock",
    "low stock":        "low_stock",
    "low_stock":        "low_stock",
    "only":             "low_stock",  # "Only 3 left in stock"
    "out of stock":     "out_of_stock",
    "out_of_stock":     "out_of_stock",
    "unavailable":      "out_of_stock",
    "currently unavailable": "out_of_stock",
}

def _normalise_stock(raw: str | None) -> str:
    if not raw:
        return "unknown"
    lower = raw.lower()
    for fragment, canonical in _STOCK_MAP.items():
        if fragment in lower:
            return canonical
    return "unknown"

normalise_stock_udf = F.udf(_normalise_stock, StringType())

# COMMAND ----------
# MAGIC %md ## Clean bronze.products → silver.price_history (source = 'product')

# COMMAND ----------

bronze_products = (
    spark.table("bronze.products")
    .filter(F.col("asin").isNotNull())
    .filter(F.to_date(F.col("scraped_at")) == F.lit(SCRAPE_DATE))
    .filter(F.col("price").isNotNull() & (F.col("price") > 0))
)

silver_from_products = (
    bronze_products
    .withColumn("scrape_date",  F.to_date(F.col("scraped_at")))
    .withColumn("stock",        normalise_stock_udf(F.col("stock")))
    .withColumn("source",       F.lit("product"))
    .withColumn("parent_asin",  F.lit(None).cast(StringType()))
    .select(
        "asin",
        F.col("price").cast(DoubleType()).alias("price"),
        "currency",
        "stock",
        F.col("rating").cast(DoubleType()).alias("rating"),
        "source",
        "parent_asin",
        "scrape_date",
        "scraped_at",
    )
    # Keep only the latest scrape per (asin, scrape_date) in case of multiple scrapes per day
    .withColumn(
        "_row_num",
        F.row_number().over(
            __import__("pyspark.sql", fromlist=["Window"])
            .Window.partitionBy("asin", "scrape_date")
            .orderBy(F.desc("scraped_at"))
        )
    )
    .filter(F.col("_row_num") == 1)
    .drop("_row_num")
)

product_count = silver_from_products.count()
print(f"Cleaned product rows: {product_count}")

# COMMAND ----------
# MAGIC %md ## Clean bronze.competitors → silver.price_history (source = 'competitor')

# COMMAND ----------

bronze_competitors = (
    spark.table("bronze.competitors")
    .filter(F.col("asin").isNotNull() & F.col("parent_asin").isNotNull())
    .filter(F.to_date(F.col("fetched_at")) == F.lit(SCRAPE_DATE))
    .filter(F.col("price").isNotNull() & (F.col("price") > 0))
)

silver_from_competitors = (
    bronze_competitors
    .withColumn("scrape_date", F.to_date(F.col("fetched_at")))
    .withColumn("stock",       F.lit("unknown"))
    .withColumn("rating",      F.col("rating").cast(DoubleType()))
    .withColumn("source",      F.lit("competitor"))
    .withColumn("scraped_at",  F.col("fetched_at"))
    .select(
        "asin",
        F.col("price").cast(DoubleType()).alias("price"),
        "currency",
        "stock",
        "rating",
        "source",
        "parent_asin",
        "scrape_date",
        "scraped_at",
    )
    .withColumn(
        "_row_num",
        F.row_number().over(
            __import__("pyspark.sql", fromlist=["Window"])
            .Window.partitionBy("asin", "parent_asin", "scrape_date")
            .orderBy(F.desc("scraped_at"))
        )
    )
    .filter(F.col("_row_num") == 1)
    .drop("_row_num")
)

competitor_count = silver_from_competitors.count()
print(f"Cleaned competitor rows: {competitor_count}")

# COMMAND ----------
# MAGIC %md ## MERGE INTO silver.price_history
# MAGIC
# MAGIC Natural key: `(asin, scrape_date, source)`.
# MAGIC Running this twice with the same data updates the existing rows (no duplicates).

# COMMAND ----------

combined = silver_from_products.union(silver_from_competitors)

combined.createOrReplaceTempView("_silver_staging")

spark.sql(f"""
MERGE INTO silver.price_history AS target
USING _silver_staging AS source
  ON  target.asin       = source.asin
  AND target.scrape_date = source.scrape_date
  AND target.source     = source.source
  AND (target.parent_asin = source.parent_asin
       OR (target.parent_asin IS NULL AND source.parent_asin IS NULL))
WHEN MATCHED THEN UPDATE SET
  target.price        = source.price,
  target.currency     = source.currency,
  target.stock        = source.stock,
  target.rating       = source.rating,
  target.scraped_at   = source.scraped_at,
  target._updated_at  = current_timestamp()
WHEN NOT MATCHED THEN INSERT (
  asin, price, currency, stock, rating, source, parent_asin,
  scrape_date, scraped_at, _updated_at
) VALUES (
  source.asin, source.price, source.currency, source.stock, source.rating,
  source.source, source.parent_asin, source.scrape_date, source.scraped_at,
  current_timestamp()
)
""")

print("✓ MERGE INTO silver.price_history complete")

# COMMAND ----------
# MAGIC %md ## Build silver.competitor_map
# MAGIC
# MAGIC One row per `(parent_asin, competitor_asin, scrape_date)` with price ranking.
# MAGIC `price_rank = 1` means cheapest competitor.

# COMMAND ----------

from pyspark.sql import Window

w_parent_date = Window.partitionBy("parent_asin", "scrape_date").orderBy("price")

# Pull parent product price for diff calculation
parent_prices = (
    spark.table("silver.price_history")
    .filter(F.col("source") == "product")
    .filter(F.col("scrape_date") == F.lit(SCRAPE_DATE))
    .select(F.col("asin").alias("_parent_asin"), F.col("price").alias("_parent_price"), "scrape_date")
)

competitor_map_df = (
    spark.table("silver.price_history")
    .filter(F.col("source") == "competitor")
    .filter(F.col("scrape_date") == F.lit(SCRAPE_DATE))
    .join(
        parent_prices,
        (F.col("parent_asin") == F.col("_parent_asin")) & (F.col("scrape_date") == F.col("scrape_date")),
        how="left"
    )
    .withColumn(
        "price_diff_pct",
        F.when(
            F.col("_parent_price").isNotNull() & (F.col("_parent_price") > 0),
            (F.col("price") - F.col("_parent_price")) / F.col("_parent_price") * 100
        ).otherwise(F.lit(None).cast(DoubleType()))
    )
    .withColumn("price_rank", F.rank().over(w_parent_date))
    .select(
        "parent_asin",
        F.col("asin"),
        F.col("rating"),
        F.col("price"),
        F.col("currency"),
        "price_diff_pct",
        "price_rank",
        "scrape_date",
    )
)

competitor_map_df.createOrReplaceTempView("_competitor_map_staging")

spark.sql(f"""
MERGE INTO silver.competitor_map AS target
USING _competitor_map_staging AS source
  ON  target.parent_asin = source.parent_asin
  AND target.asin        = source.asin
  AND target.scrape_date  = source.scrape_date
WHEN MATCHED THEN UPDATE SET
  target.price          = source.price,
  target.currency       = source.currency,
  target.rating         = source.rating,
  target.price_diff_pct = source.price_diff_pct,
  target.price_rank     = source.price_rank,
  target._updated_at    = current_timestamp()
WHEN NOT MATCHED THEN INSERT (
  parent_asin, asin, price, currency, rating,
  price_diff_pct, price_rank, scrape_date, _updated_at
) VALUES (
  source.parent_asin, source.asin, source.price, source.currency, source.rating,
  source.price_diff_pct, source.price_rank, source.scrape_date, current_timestamp()
)
""")

print("✓ MERGE INTO silver.competitor_map complete")

# COMMAND ----------
# MAGIC %md ## Verify

# COMMAND ----------

print(f"=== silver.price_history — rows for {SCRAPE_DATE} ===")
spark.sql(f"""
  SELECT source, COUNT(*) AS rows, COUNT(DISTINCT asin) AS unique_asins
  FROM silver.price_history
  WHERE scrape_date = '{SCRAPE_DATE}'
  GROUP BY source
""").show()

print("=== silver.competitor_map — price rank distribution ===")
spark.sql(f"""
  SELECT price_rank, COUNT(*) AS competitors
  FROM silver.competitor_map
  WHERE scrape_date = '{SCRAPE_DATE}'
  GROUP BY price_rank
  ORDER BY price_rank
  LIMIT 10
""").show()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC Next step: run `03_gold_features.py` to compute rolling aggregates and competitive
# MAGIC pressure scores into `gold.price_features`.
