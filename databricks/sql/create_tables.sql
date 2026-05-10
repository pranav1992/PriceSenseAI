-- =============================================================================
-- PriceSenseAi — Delta Lake Table DDL
-- Run this once in a Databricks SQL editor or notebook (%sql) to create all
-- schemas and tables before running any notebook.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Schemas (layers)
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS bronze
  COMMENT 'Raw, append-only snapshots exactly as received from Oxylabs';

CREATE SCHEMA IF NOT EXISTS silver
  COMMENT 'Cleaned, deduplicated, one row per (asin, scrape_date)';

CREATE SCHEMA IF NOT EXISTS gold
  COMMENT 'Pre-aggregated features ready for ML and the FastAPI serving layer';


-- ---------------------------------------------------------------------------
-- BRONZE LAYER
-- Append-only: never update, never delete.
-- Every scrape run produces new rows — this is the audit trail.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bronze.products (
  asin             STRING  NOT NULL  COMMENT 'Amazon ASIN',
  title            STRING            COMMENT 'Product title at time of scrape',
  brand            STRING,
  price            DOUBLE            COMMENT 'Listed price in local currency',
  currency         STRING,
  stock            STRING            COMMENT 'Raw stock string from Oxylabs',
  rating           DOUBLE,
  url              STRING,
  images           ARRAY<STRING>,
  categories       ARRAY<STRING>,
  category_path    ARRAY<STRING>,
  buybox           STRING            COMMENT 'JSON-encoded buybox offers',
  product_overview STRING            COMMENT 'JSON-encoded product specs',
  amazon_domain    STRING,
  geo_location     STRING,
  scraped_at       TIMESTAMP NOT NULL COMMENT 'UTC timestamp of the Oxylabs API call',
  _ingested_at     TIMESTAMP         COMMENT 'UTC timestamp when row landed in Delta'
)
USING DELTA
COMMENT 'Raw product snapshots — append-only, never modified after write'
TBLPROPERTIES (
  'delta.appendOnly'                       = 'true',
  'delta.autoOptimize.optimizeWrite'       = 'true'
);


CREATE TABLE IF NOT EXISTS bronze.competitors (
  parent_asin   STRING  NOT NULL COMMENT 'ASIN of the product this competitor was found for',
  asin          STRING  NOT NULL COMMENT 'Competitor ASIN',
  title         STRING,
  brand         STRING,
  price         DOUBLE,
  currency      STRING,
  rating        DOUBLE,
  url           STRING,
  images        ARRAY<STRING>,
  amazon_domain STRING,
  fetched_at    TIMESTAMP NOT NULL COMMENT 'UTC timestamp of the Oxylabs search call',
  _ingested_at  TIMESTAMP         COMMENT 'UTC timestamp when row landed in Delta'
)
USING DELTA
COMMENT 'Raw competitor search results — append-only, never modified after write'
TBLPROPERTIES (
  'delta.appendOnly'                 = 'true',
  'delta.autoOptimize.optimizeWrite' = 'true'
);


-- ---------------------------------------------------------------------------
-- SILVER LAYER
-- One cleaned row per (asin, scrape_date).
-- Written via MERGE INTO from the silver cleaning notebook — idempotent.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS silver.price_history (
  asin         STRING    NOT NULL COMMENT 'Amazon ASIN',
  price        DOUBLE    NOT NULL COMMENT 'Cleaned price — nulls and zeros excluded',
  currency     STRING    NOT NULL,
  stock        STRING              COMMENT 'Normalised stock level: in_stock | low_stock | out_of_stock | unknown',
  rating       DOUBLE,
  source       STRING    NOT NULL  COMMENT 'product (own) or competitor',
  parent_asin  STRING              COMMENT 'Set only when source = competitor',
  scrape_date  DATE      NOT NULL  COMMENT 'UTC date of the scrape (partition key)',
  scraped_at   TIMESTAMP NOT NULL,
  _updated_at  TIMESTAMP           COMMENT 'UTC timestamp of last MERGE write'
)
USING DELTA
PARTITIONED BY (scrape_date)
COMMENT 'Deduplicated daily price snapshots — the source of truth for all analytics'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true'
);


CREATE TABLE IF NOT EXISTS silver.competitor_map (
  parent_asin    STRING  NOT NULL COMMENT 'ASIN of the product being tracked',
  asin           STRING  NOT NULL COMMENT 'Competitor ASIN',
  title          STRING,
  brand          STRING,
  price          DOUBLE,
  currency       STRING,
  rating         DOUBLE,
  price_diff_pct DOUBLE            COMMENT '(competitor_price - parent_price) / parent_price * 100',
  price_rank     INT               COMMENT 'Price rank among competitors (1 = cheapest)',
  scrape_date    DATE    NOT NULL  COMMENT 'Partition key',
  _updated_at    TIMESTAMP
)
USING DELTA
PARTITIONED BY (scrape_date)
COMMENT 'Per-day competitor landscape with price ranking — written by MERGE INTO'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true'
);


-- ---------------------------------------------------------------------------
-- GOLD LAYER
-- Pre-aggregated features per (asin, scrape_date).
-- Read by the FastAPI analysis endpoint and the ML training pipeline.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gold.price_features (
  asin                STRING  NOT NULL COMMENT 'Amazon ASIN',
  scrape_date         DATE    NOT NULL COMMENT 'Partition key',
  current_price       DOUBLE,
  currency            STRING,
  -- Time-series features
  price_7d_ma         DOUBLE  COMMENT '7-day moving average price',
  price_7d_volatility DOUBLE  COMMENT '7-day price standard deviation',
  price_momentum      DOUBLE  COMMENT '(price_today - price_7d_ago) / price_7d_ago',
  -- Competitive features
  comp_median_price   DOUBLE  COMMENT 'Median price across all competitors that day',
  comp_avg_price      DOUBLE,
  comp_min_price      DOUBLE,
  comp_max_price      DOUBLE,
  comp_count          INT     COMMENT 'Number of competitors with a valid price',
  competitors_below   INT     COMMENT 'Competitors priced strictly below this product',
  comp_pressure_score DOUBLE  COMMENT 'competitors_below / comp_count  (0 = cheapest, 1 = most expensive)',
  -- Derived suggestions
  suggested_price     DOUBLE  COMMENT 'comp_median adjusted for rating premium',
  price_position      STRING  COMMENT 'above_market | at_market | below_market',
  _computed_at        TIMESTAMP COMMENT 'UTC timestamp when row was last recomputed'
)
USING DELTA
PARTITIONED BY (scrape_date)
COMMENT 'ML-ready feature table — refreshed daily after silver pipeline completes'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true'
);


-- ---------------------------------------------------------------------------
-- Verify all tables were created
-- ---------------------------------------------------------------------------
SHOW TABLES IN bronze;
SHOW TABLES IN silver;
SHOW TABLES IN gold;
