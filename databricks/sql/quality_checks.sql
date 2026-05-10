-- =============================================================================
-- PriceSenseAi — Data Quality Checks
-- Run after each pipeline run to catch bad data before it reaches Silver/Gold.
-- Each query should return 0 rows. If any rows are returned, the check failed.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- BRONZE quality checks
-- ---------------------------------------------------------------------------

-- Check 1: No null ASINs in bronze.products
SELECT 'bronze.products: null ASIN' AS check_name, COUNT(*) AS failing_rows
FROM bronze.products
WHERE asin IS NULL
HAVING COUNT(*) > 0;

-- Check 2: No null ASINs in bronze.competitors
SELECT 'bronze.competitors: null ASIN' AS check_name, COUNT(*) AS failing_rows
FROM bronze.competitors
WHERE asin IS NULL OR parent_asin IS NULL
HAVING COUNT(*) > 0;

-- Check 3: No obviously corrupt prices (zero or negative)
SELECT 'bronze.products: zero or negative price' AS check_name, COUNT(*) AS failing_rows
FROM bronze.products
WHERE price IS NOT NULL AND price <= 0
HAVING COUNT(*) > 0;

SELECT 'bronze.competitors: zero or negative price' AS check_name, COUNT(*) AS failing_rows
FROM bronze.competitors
WHERE price IS NOT NULL AND price <= 0
HAVING COUNT(*) > 0;

-- Check 4: No future scraped_at timestamps (clock skew / bad data)
SELECT 'bronze.products: future scraped_at' AS check_name, COUNT(*) AS failing_rows
FROM bronze.products
WHERE scraped_at > current_timestamp() + INTERVAL 1 HOUR
HAVING COUNT(*) > 0;

-- Check 5: ASIN format — Amazon ASINs are exactly 10 alphanumeric characters
SELECT 'bronze.products: invalid ASIN format' AS check_name, COUNT(*) AS failing_rows
FROM bronze.products
WHERE NOT (asin RLIKE '^[A-Z0-9]{10}$')
HAVING COUNT(*) > 0;


-- ---------------------------------------------------------------------------
-- SILVER quality checks
-- ---------------------------------------------------------------------------

-- Check 6: No duplicate (asin, scrape_date) rows — MERGE INTO should prevent this
SELECT 'silver.price_history: duplicate (asin, scrape_date, source)' AS check_name, COUNT(*) AS failing_rows
FROM (
  SELECT asin, scrape_date, source, COUNT(*) AS cnt
  FROM silver.price_history
  GROUP BY asin, scrape_date, source
  HAVING cnt > 1
)
HAVING COUNT(*) > 0;

-- Check 7: No null prices in silver (cleaning should have removed them)
SELECT 'silver.price_history: null price' AS check_name, COUNT(*) AS failing_rows
FROM silver.price_history
WHERE price IS NULL
HAVING COUNT(*) > 0;

-- Check 8: Price range sanity — flag prices outside $0.01–$100,000
SELECT 'silver.price_history: price out of range' AS check_name, COUNT(*) AS failing_rows
FROM silver.price_history
WHERE price < 0.01 OR price > 100000
HAVING COUNT(*) > 0;

-- Check 9: Source must be 'product' or 'competitor'
SELECT 'silver.price_history: invalid source' AS check_name, COUNT(*) AS failing_rows
FROM silver.price_history
WHERE source NOT IN ('product', 'competitor')
HAVING COUNT(*) > 0;


-- ---------------------------------------------------------------------------
-- GOLD quality checks
-- ---------------------------------------------------------------------------

-- Check 10: comp_pressure_score must be between 0 and 1
SELECT 'gold.price_features: comp_pressure_score out of range' AS check_name, COUNT(*) AS failing_rows
FROM gold.price_features
WHERE comp_pressure_score IS NOT NULL
  AND (comp_pressure_score < 0 OR comp_pressure_score > 1)
HAVING COUNT(*) > 0;

-- Check 11: price_position must be a known value
SELECT 'gold.price_features: invalid price_position' AS check_name, COUNT(*) AS failing_rows
FROM gold.price_features
WHERE price_position IS NOT NULL
  AND price_position NOT IN ('above_market', 'at_market', 'below_market')
HAVING COUNT(*) > 0;

-- Check 12: No duplicate (asin, scrape_date) in gold
SELECT 'gold.price_features: duplicate (asin, scrape_date)' AS check_name, COUNT(*) AS failing_rows
FROM (
  SELECT asin, scrape_date, COUNT(*) AS cnt
  FROM gold.price_features
  GROUP BY asin, scrape_date
  HAVING cnt > 1
)
HAVING COUNT(*) > 0;


-- ---------------------------------------------------------------------------
-- Summary view — run this for a quick pass/fail dashboard
-- ---------------------------------------------------------------------------
-- Paste all the queries above into a single UNION ALL and alias as `quality_report`
-- to see all checks in one result set. Each row with failing_rows > 0 is a failure.
