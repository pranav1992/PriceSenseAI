# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Gold Features
# MAGIC
# MAGIC **Layer:** Gold (ML-ready aggregated features)
# MAGIC
# MAGIC **What this does:**
# MAGIC Reads from `silver.price_history` and `silver.competitor_map`, engineers time-series
# MAGIC and competitive features using Spark window functions, and upserts the result into
# MAGIC `gold.price_features` — one row per `(asin, scrape_date)`.
# MAGIC
# MAGIC **Features engineered:**
# MAGIC - `price_7d_ma` — 7-day moving average price
# MAGIC - `price_7d_volatility` — 7-day price standard deviation
# MAGIC - `price_momentum` — % change from 7 days ago
# MAGIC - `comp_median_price`, `comp_avg_price`, `comp_min_price`, `comp_max_price` — competitor landscape
# MAGIC - `comp_count`, `competitors_below` — competitive position counts
# MAGIC - `comp_pressure_score` — fraction of competitors priced below (0 = cheapest, 1 = most expensive)
# MAGIC - `suggested_price` — median competitor price adjusted for rating premium
# MAGIC - `price_position` — above_market | at_market | below_market (±5% threshold)
# MAGIC
# MAGIC **Run:** Daily after silver pipeline completes (see `../databricks.yml`)

# COMMAND ----------
# MAGIC %md ## Parameters

# COMMAND ----------

from datetime import datetime, timezone

from pyspark.sql import Window, functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType

# COMMAND ----------

dbutils.widgets.text("scrape_date", "", "Scrape Date (YYYY-MM-DD, blank = today UTC)")
SCRAPE_DATE = dbutils.widgets.get("scrape_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

print(f"Scrape date: {SCRAPE_DATE}")

# COMMAND ----------
# MAGIC %md ## Time-series features
# MAGIC
# MAGIC Window: ordered by `scrape_date` per ASIN, looking back over the last 7 rows
# MAGIC (inclusive of today). Requires at least 7 days of silver history for meaningful
# MAGIC values — earlier dates will have non-null moving averages over fewer days, which
# MAGIC is correct behaviour (expanding window).

# COMMAND ----------

# All own-product price history (not just today) — needed for rolling windows
own_prices = (
    spark.table("silver.price_history")
    .filter(F.col("source") == "product")
    .filter(F.col("price").isNotNull())
    .select("asin", "price", "rating", "currency", "stock", "scrape_date")
)

w_asin_time    = Window.partitionBy("asin").orderBy("scrape_date")
w_asin_7d      = w_asin_time.rowsBetween(-6, 0)   # up to 7 rows including current

own_with_ts = (
    own_prices
    .withColumn("price_7d_ma",        F.avg("price").over(w_asin_7d))
    .withColumn("price_7d_volatility", F.stddev("price").over(w_asin_7d))
    .withColumn("_price_7d_ago",       F.lag("price", 7).over(w_asin_time))
    .withColumn(
        "price_momentum",
        F.when(
            F.col("_price_7d_ago").isNotNull() & (F.col("_price_7d_ago") > 0),
            (F.col("price") - F.col("_price_7d_ago")) / F.col("_price_7d_ago")
        ).otherwise(F.lit(None).cast(DoubleType()))
    )
    .drop("_price_7d_ago")
)

# Keep only today's row after computing windows over all history
today_own = own_with_ts.filter(F.col("scrape_date") == F.lit(SCRAPE_DATE))

print(f"Own product rows for {SCRAPE_DATE}: {today_own.count()}")

# COMMAND ----------
# MAGIC %md ## Competitive features
# MAGIC
# MAGIC Aggregate competitor prices per `(parent_asin, scrape_date)` to get the
# MAGIC market landscape for each product today.

# COMMAND ----------

comp_agg = (
    spark.table("silver.competitor_map")
    .filter(F.col("scrape_date") == F.lit(SCRAPE_DATE))
    .filter(F.col("price").isNotNull())
    .groupBy("parent_asin", "scrape_date")
    .agg(
        F.expr("percentile_approx(price, 0.5)").cast(DoubleType()).alias("comp_median_price"),
        F.avg("price").cast(DoubleType()).alias("comp_avg_price"),
        F.min("price").cast(DoubleType()).alias("comp_min_price"),
        F.max("price").cast(DoubleType()).alias("comp_max_price"),
        F.count("*").cast(IntegerType()).alias("comp_count"),
        F.avg("rating").cast(DoubleType()).alias("comp_avg_rating"),
    )
)

# COMMAND ----------
# MAGIC %md ## Competitors below + pressure score
# MAGIC
# MAGIC Join competitor-level rows back to get count of competitors cheaper than the product.

# COMMAND ----------

today_own_prices = today_own.select(
    F.col("asin").alias("_own_asin"),
    F.col("price").alias("_own_price"),
    "scrape_date",
)

comp_below = (
    spark.table("silver.competitor_map")
    .filter(F.col("scrape_date") == F.lit(SCRAPE_DATE))
    .filter(F.col("price").isNotNull())
    .join(
        today_own_prices,
        (F.col("parent_asin") == F.col("_own_asin")) &
        (F.col("silver.competitor_map.scrape_date") == F.col("silver.competitor_map.scrape_date")),
        how="left"
    )
    .withColumn("is_below", (F.col("price") < F.col("_own_price")).cast(IntegerType()))
    .groupBy("parent_asin")
    .agg(F.sum("is_below").cast(IntegerType()).alias("competitors_below"))
)

# COMMAND ----------
# MAGIC %md ## Suggested price + price position
# MAGIC
# MAGIC - `suggested_price`: competitor median price, with +3% premium if the product's
# MAGIC   rating exceeds the average competitor rating by more than 0.3 stars.
# MAGIC - `price_position`: above_market if own price > median * 1.05,
# MAGIC                      below_market if < median * 0.95, otherwise at_market.

# COMMAND ----------

RATING_PREMIUM_THRESHOLD = 0.3
RATING_PREMIUM_PCT        = 0.03
PRICE_POSITION_BAND       = 0.05

gold = (
    today_own
    .join(comp_agg,  today_own["asin"] == comp_agg["parent_asin"],  how="left")
    .join(comp_below, today_own["asin"] == comp_below["parent_asin"], how="left")
    .withColumn(
        "comp_pressure_score",
        F.when(
            F.col("comp_count").isNotNull() & (F.col("comp_count") > 0),
            F.col("competitors_below").cast(DoubleType()) / F.col("comp_count")
        ).otherwise(F.lit(None).cast(DoubleType()))
    )
    .withColumn(
        "_rating_premium",
        F.when(
            F.col("rating").isNotNull() & F.col("comp_avg_rating").isNotNull() &
            ((F.col("rating") - F.col("comp_avg_rating")) > RATING_PREMIUM_THRESHOLD),
            F.lit(RATING_PREMIUM_PCT)
        ).otherwise(F.lit(0.0))
    )
    .withColumn(
        "suggested_price",
        F.when(
            F.col("comp_median_price").isNotNull(),
            F.round(F.col("comp_median_price") * (1 + F.col("_rating_premium")), 2)
        ).otherwise(F.lit(None).cast(DoubleType()))
    )
    .withColumn(
        "price_position",
        F.when(F.col("comp_median_price").isNull(), F.lit(None).cast(StringType()))
        .when(F.col("price") > F.col("comp_median_price") * (1 + PRICE_POSITION_BAND), F.lit("above_market"))
        .when(F.col("price") < F.col("comp_median_price") * (1 - PRICE_POSITION_BAND), F.lit("below_market"))
        .otherwise(F.lit("at_market"))
    )
    .select(
        "asin",
        "scrape_date",
        F.col("price").alias("current_price"),
        "currency",
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
        "suggested_price",
        "price_position",
    )
    .drop("_rating_premium")
)

gold_count = gold.count()
print(f"Gold rows to write: {gold_count}")
gold.show(truncate=False)

# COMMAND ----------
# MAGIC %md ## MERGE INTO gold.price_features

# COMMAND ----------

gold.createOrReplaceTempView("_gold_staging")

spark.sql("""
MERGE INTO gold.price_features AS target
USING _gold_staging AS source
  ON  target.asin        = source.asin
  AND target.scrape_date = source.scrape_date
WHEN MATCHED THEN UPDATE SET
  target.current_price       = source.current_price,
  target.currency            = source.currency,
  target.price_7d_ma         = source.price_7d_ma,
  target.price_7d_volatility = source.price_7d_volatility,
  target.price_momentum      = source.price_momentum,
  target.comp_median_price   = source.comp_median_price,
  target.comp_avg_price      = source.comp_avg_price,
  target.comp_min_price      = source.comp_min_price,
  target.comp_max_price      = source.comp_max_price,
  target.comp_count          = source.comp_count,
  target.competitors_below   = source.competitors_below,
  target.comp_pressure_score = source.comp_pressure_score,
  target.suggested_price     = source.suggested_price,
  target.price_position      = source.price_position,
  target._computed_at        = current_timestamp()
WHEN NOT MATCHED THEN INSERT (
  asin, scrape_date, current_price, currency,
  price_7d_ma, price_7d_volatility, price_momentum,
  comp_median_price, comp_avg_price, comp_min_price, comp_max_price,
  comp_count, competitors_below, comp_pressure_score,
  suggested_price, price_position, _computed_at
) VALUES (
  source.asin, source.scrape_date, source.current_price, source.currency,
  source.price_7d_ma, source.price_7d_volatility, source.price_momentum,
  source.comp_median_price, source.comp_avg_price, source.comp_min_price, source.comp_max_price,
  source.comp_count, source.competitors_below, source.comp_pressure_score,
  source.suggested_price, source.price_position, current_timestamp()
)
""")

print("✓ MERGE INTO gold.price_features complete")

# COMMAND ----------
# MAGIC %md ## Verify: feature completeness

# COMMAND ----------

print(f"=== gold.price_features for {SCRAPE_DATE} ===")
spark.sql(f"""
  SELECT
    asin,
    current_price,
    ROUND(price_7d_ma, 2)         AS price_7d_ma,
    ROUND(price_7d_volatility, 4) AS price_7d_vol,
    ROUND(price_momentum * 100, 2) AS momentum_pct,
    comp_count,
    ROUND(comp_median_price, 2)   AS comp_median,
    ROUND(comp_pressure_score, 3) AS pressure,
    suggested_price,
    price_position
  FROM gold.price_features
  WHERE scrape_date = '{SCRAPE_DATE}'
  ORDER BY asin
""").show(truncate=False)

# COMMAND ----------
# MAGIC %md ## Verify: time travel is working

# COMMAND ----------

print("=== gold.price_features history ===")
spark.sql("DESCRIBE HISTORY gold.price_features").select(
    "version", "timestamp", "operation", "operationMetrics"
).show(10, truncate=False)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC Next step: run `04_price_model.py` to train an XGBoost model on these features
# MAGIC and log the run to MLflow.
