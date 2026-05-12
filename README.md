# PriceSense AI

### Real-Time Product Intelligence & Competitor Analysis Platform

---

## Overview

**PriceSense AI** is a production-grade data platform that ingests product data from Oxylabs, processes it using a **Medallion Architecture (Bronze → Silver → Gold)** on Databricks, and provides AI-powered price insights and competitor analytics for e-commerce products.

---

## Key Features

* Daily automated scraping via Oxylabs API (products + competitors)
* Medallion Architecture on Delta Lake (Bronze → Silver → Gold)
* End-to-end Databricks Workflows — no external scheduler required
* Time-series price tracking with 7-day rolling features
* XGBoost price optimisation model tracked in MLflow
* Competitor price ranking and market position scoring
* FastAPI backend serving gold-layer features
* React/Next.js analytics dashboard with chat interface

---

## Architecture

```
Oxylabs API
     ↓  [scrape_raw — 01:00 UTC]
JSON snapshots in cloud storage (S3 / ADLS)
     ↓  [ingest_bronze]
Bronze Delta tables  (append-only, immutable)
     ↓  [silver_clean]
Silver Delta tables  (deduplicated, MERGE INTO)
     ↓  [gold_features]
Gold Delta table     (ML-ready features, suggested prices)
     ↓
FastAPI  →  React dashboard
```

All four stages run as a single Databricks job, sequentially, scheduled at **01:00 UTC daily**.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping | Oxylabs Realtime API |
| Orchestration | Databricks Workflows (Asset Bundles) |
| Processing | Apache Spark 15.4 LTS (Databricks) |
| Storage | Delta Lake (Unity Catalog or Hive metastore) |
| ML | XGBoost + MLflow Model Registry |
| Backend API | FastAPI + PostgreSQL |
| Frontend | Next.js + Tailwind CSS |

---

## Data Model

### Bronze (append-only)
| Table | Description |
|---|---|
| `bronze.products` | Raw product snapshots from Oxylabs |
| `bronze.competitors` | Raw competitor search results |

### Silver (deduplicated)
| Table | Description |
|---|---|
| `silver.price_history` | One row per `(asin, scrape_date, source)` |
| `silver.competitor_map` | Competitor pricing landscape with price rank and % diff |

### Gold (ML-ready)
| Table | Description |
|---|---|
| `gold.price_features` | 7-day rolling features, competitive signals, `suggested_price` |

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/pranav1992/PriceSenseAI.git
cd PriceSenseAI
uv sync
```

### 2. Configure environment

```bash
# .env (project root)
OXYLABS_USERNAME=your_username
OXYLABS_PASSWORD=your_password
OXYLABS_API_URL=https://realtime.oxylabs.io/v1/queries

DATABASE_URL=postgresql://pricesense:pricesense@localhost:5432/pricesense
CORS_ORIGINS=http://localhost:3000

DATABRICKS_HOST=https://<workspace>.azuredatabricks.net
DATABRICKS_TOKEN=<personal-access-token>
```

### 3. Add tracked ASINs

Edit `ingestion/asins.txt` — one ASIN per line:

```
B0FY52GZFG
B08N5WRWNW
```

### 4. Run locally (dev)

Frontend, backend, and database:

```bash
./scripts/dev.sh
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Database | localhost:5432 |

### 5. Run ingestion locally

```bash
# Single ASIN
uv run python ingestion/jobs/ingest_products.py --asin B0FY52GZFG --output ./data

# All tracked ASINs
uv run python ingestion/jobs/ingest_products.py --manifest ingestion/asins.txt --output ./data
```

Writes to `./data/products/YYYY-MM-DD/{asin}.json` and `./data/competitors/YYYY-MM-DD/{asin}_competitors.json`.

---

## Databricks Deployment

### 1. Create secret scope for Oxylabs credentials

```bash
databricks secrets create-scope pricesense
databricks secrets put-secret pricesense OXYLABS_USERNAME --string-value <username>
databricks secrets put-secret pricesense OXYLABS_PASSWORD --string-value <password>
```

### 2. Deploy the pipeline

```bash
# Development workspace
databricks bundle deploy --target dev

# Production
databricks bundle deploy --target prod \
  --var storage_path=s3://your-bucket/pricesense
```

This deploys two jobs to your Databricks workspace:

| Job | Schedule | Purpose |
|---|---|---|
| `[PriceSenseAi] Full Pipeline` | 01:00 UTC daily | scrape → bronze → silver → gold |
| `[PriceSenseAi] Bronze Ingestion (manual)` | unscheduled | re-ingest a specific date ad-hoc |

### 3. Run manually

```bash
databricks bundle run full_pipeline --target dev
```

### Pipeline task DAG

```
scrape_raw  →  ingest_bronze  →  silver_clean  →  gold_features
```

---

## ML Model

Train the XGBoost price optimisation model (run weekly or on-demand in Databricks):

```
databricks/notebooks/04_price_model.py
```

Logs metrics and registers the model in the MLflow Model Registry as `PriceOptimizationModel`. The FastAPI backend serves predictions from the registered model.

---

## Testing

```bash
# All tests
cd backend && uv run pytest

# Unit or integration only
uv run pytest -m unit
uv run pytest -m integration
```

---

## Project Structure

```
PriceSenseAI/
├── ingestion/
│   ├── asins.txt                  # Tracked ASINs — one per line
│   ├── jobs/
│   │   ├── ingest_products.py     # Full product + competitor scrape
│   │   ├── ingest_prices.py       # Lightweight price-only snapshot
│   │   └── ingest_reviews.py      # (placeholder)
│   └── oxylabs_client/
│       └── client.py              # Oxylabs API wrapper
│
├── databricks/
│   ├── databricks.yml             # Asset Bundle — job definitions (canonical)
│   ├── notebooks/
│   │   ├── 01_bronze_ingestion.py
│   │   ├── 02_silver_cleaning.py
│   │   ├── 03_gold_features.py
│   │   └── 04_price_model.py
│   ├── jobs/
│   │   ├── bronze_job.yml         # Reference doc (not deployed directly)
│   │   └── silver_gold_job.yml    # Reference doc (not deployed directly)
│   └── sql/
│       ├── create_tables.sql
│       └── quality_checks.sql
│
├── backend/
│   └── app/
│       ├── main.py
│       ├── routes/                # products, competitors, analysis
│       └── core/database.py
│
├── frontend/
│   └── app/
│       ├── page.tsx
│       ├── products/
│       ├── competitors/
│       ├── analytics/
│       └── chat/
│
├── scripts/
│   ├── dev.sh                     # Dev: DB in Docker, services run locally
│   └── staging.sh                 # Staging: all services in Docker
│
├── docker-compose.yml
└── pyproject.toml
```

---

## Future Improvements

* Streaming ingestion (Kafka / Databricks Auto Loader)
* Multi-marketplace support (UK, DE, JP)
* Reinforcement learning for dynamic pricing
* Advanced forecasting (Prophet / NeuralProphet)

---

## Author

**Pranav Chourasia** — Data Engineer | AI/ML Enthusiast
