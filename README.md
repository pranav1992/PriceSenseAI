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
* XGBoost price optimisation model with automated training, evaluation and promotion
* MLflow Model Registry with quality gates (RMSE + MAPE thresholds)
* Daily batch scoring writing predictions to `gold.price_predictions`
* Data drift detection (KS test) and rolling model performance monitoring
* FastAPI backend serving gold-layer features and predictions
* React/Next.js analytics dashboard with chat interface

---

## Architecture

```
Oxylabs API
     ↓  [01:00 UTC daily]
JSON snapshots in cloud storage (S3 / ADLS)
     ↓
Bronze Delta tables  (append-only, immutable)
     ↓
Silver Delta tables  (deduplicated via MERGE INTO)
     ↓
Gold Delta tables    (ML-ready features + predictions)
     ↓
FastAPI  →  React dashboard
```

Four Databricks Workflow jobs orchestrate the full lifecycle:

```
[Daily 01:00]   scrape_raw → ingest_bronze → silver_clean → gold_features

[Weekly Mon]    feature_store_register → train_model → evaluate_model → (auto-promote)

[Daily 03:00]   batch_score → gold.price_predictions

[Daily 04:00]   data_drift_check → model_performance_check
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping | Oxylabs Realtime API |
| Orchestration | Databricks Workflows (Asset Bundles) |
| Processing | Apache Spark 15.4 LTS (Databricks) |
| Storage | Delta Lake (Unity Catalog or Hive metastore) |
| ML Training | XGBoost + scikit-learn |
| ML Tracking | MLflow Experiments + Model Registry |
| ML Serving | MLflow batch inference |
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
| `gold.price_predictions` | Daily model predictions with model version tracking |

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
# All tracked ASINs
uv run python ingestion/jobs/ingest_products.py --manifest ingestion/asins.txt --output ./data

# Single ASIN
uv run python ingestion/jobs/ingest_products.py --asin B0FY52GZFG --output ./data
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

### 2. Deploy the bundle

```bash
# Development workspace
databricks bundle deploy --target dev

# Production
databricks bundle deploy --target prod \
  --var storage_path=s3://your-bucket/pricesense
```

This deploys four jobs to your Databricks workspace:

| Job | Schedule | Purpose |
|---|---|---|
| `[PriceSenseAi] Full Pipeline` | Daily 01:00 UTC | scrape → bronze → silver → gold |
| `[PriceSenseAi] Training Pipeline` | Weekly Mon 02:00 UTC | feature store → train → evaluate → promote |
| `[PriceSenseAi] Scoring Pipeline` | Daily 03:00 UTC | batch score → write predictions |
| `[PriceSenseAi] Monitoring Pipeline` | Daily 04:00 UTC | drift detection + performance check |
| `[PriceSenseAi] Bronze Ingestion (manual)` | unscheduled | re-ingest a specific date ad-hoc |

### 3. Run a job manually

```bash
databricks bundle run full_pipeline --target dev
databricks bundle run training_pipeline --target dev
databricks bundle run scoring_pipeline --target dev
```

---

## ML Pipeline

### Training (`databricks/notebooks/training/`)

| Notebook | What it does |
|---|---|
| `04_feature_store.py` | Registers `gold.price_features` in Databricks Feature Store |
| `05_train_price_model.py` | Trains XGBoost, logs run to MLflow, registers model version |
| `06_evaluate_model.py` | Loads latest version, checks RMSE + MAPE quality gates, auto-promotes to Production |

Quality gates are configured in `databricks/configs/model_config.yaml`:

```yaml
quality_gates:
  max_rmse: 10.0
  max_mape: 15.0
```

### Inference (`databricks/notebooks/inference/`)

| Notebook | What it does |
|---|---|
| `07_batch_scoring.py` | Loads Production model, scores today's features, writes `gold.price_predictions` |

### Monitoring (`databricks/notebooks/monitoring/`)

| Notebook | What it does |
|---|---|
| `08_data_drift.py` | KS test per feature against 30-day baseline; alerts on significant shift |
| `09_model_performance.py` | Rolling MAPE over recent predictions; triggers retraining alert if degraded |

Both monitoring notebooks log to the `/Shared/pricesense-ai/monitoring` MLflow experiment.

### Exploratory (`databricks/notebooks/exploratory/`)

Not scheduled — run interactively to understand data and justify production decisions.

| Notebook | What it answers |
|---|---|
| `EDA_01_data_overview.py` | Schema, null rates, coverage gaps, data health across all layers |
| `EDA_02_price_analysis.py` | Price distributions, time-series trends, day-of-week seasonality |
| `EDA_03_competitor_landscape.py` | Competitor count, price spread, rating-price correlation, market position |
| `EDA_04_feature_engineering.py` | Rolling window sensitivity (3d/7d/14d), position band tuning, feature correlations |
| `EDA_05_model_selection.py` | XGBoost vs baselines, hyperparameter sweeps, learning curves, residual analysis |

---

## Local ML Development

The `local/` directory is a standalone `uv` project for fast prototyping —
no Databricks cluster required. It reuses the same `src/` library as production.

```bash
cd local
uv sync                                       # install deps into local/.venv

# Generate synthetic sample data (90 days × 3 ASINs)
uv run python data/generate_sample_data.py

# Launch Jupyter
uv run jupyter notebook notebooks/

# View MLflow experiment runs
uv run mlflow ui
```

| Notebook | What it does locally |
|---|---|
| `01_feature_engineering.ipynb` | Reimplements `03_gold_features.py` in pandas |
| `02_model_experiments.ipynb` | XGBoost vs Ridge vs RandomForest + hyperparameter sweeps |
| `03_pytorch_experiments.ipynb` | MLP and LSTM alternatives; compare vs XGBoost |

---

## Testing

```bash
# Backend unit + integration tests
cd backend && uv run pytest

# ML pipeline unit tests (no Spark required)
cd local && uv run pytest ../databricks/tests/unit/ -v

# ML pipeline integration tests (requires Databricks / Delta tables)
cd databricks && python -m pytest -m integration tests/integration/
```

---

## Project Structure

```
PriceSenseAI/
├── ingestion/
│   ├── asins.txt                      # Tracked ASINs — one per line
│   ├── jobs/
│   │   ├── ingest_products.py         # Full product + competitor scrape
│   │   ├── ingest_prices.py           # Lightweight price-only snapshot
│   │   └── ingest_reviews.py          # (placeholder)
│   └── oxylabs_client/
│       └── client.py                  # Oxylabs API wrapper
│
├── databricks/
│   ├── databricks.yml                 # Asset Bundle — all job definitions (canonical)
│   ├── notebooks/
│   │   ├── ingestion/
│   │   │   └── 01_bronze_ingestion.py
│   │   ├── processing/
│   │   │   ├── 02_silver_cleaning.py
│   │   │   └── 03_gold_features.py
│   │   ├── training/
│   │   │   ├── 04_feature_store.py
│   │   │   ├── 05_train_price_model.py
│   │   │   └── 06_evaluate_model.py
│   │   ├── inference/
│   │   │   └── 07_batch_scoring.py
│   │   ├── monitoring/
│   │   │   ├── 08_data_drift.py
│   │   │   └── 09_model_performance.py
│   │   └── exploratory/               # Not scheduled — run interactively
│   │       ├── EDA_01_data_overview.py
│   │       ├── EDA_02_price_analysis.py
│   │       ├── EDA_03_competitor_landscape.py
│   │       ├── EDA_04_feature_engineering.py
│   │       └── EDA_05_model_selection.py
│   ├── src/                           # Reusable Python library imported by notebooks
│   │   ├── features/
│   │   │   ├── definitions.py         # Feature column lists, constants
│   │   │   └── validation.py          # Data quality checks
│   │   ├── models/
│   │   │   ├── price_optimizer.py     # XGBoost model class
│   │   │   └── hyperparams.py         # Default hyperparameters + search space
│   │   ├── evaluation/
│   │   │   └── metrics.py             # RMSE, MAE, MAPE, quality gate
│   │   └── utils/
│   │       ├── mlflow_utils.py        # Experiment setup, model registry helpers
│   │       └── spark_utils.py         # SparkSession factory
│   ├── configs/
│   │   ├── model_config.yaml          # Hyperparameters, quality gate thresholds
│   │   ├── feature_config.yaml        # Feature lists, rolling windows, thresholds
│   │   └── pipeline_config.yaml       # Cluster specs, cron schedules, alert config
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_features.py
│   │   │   └── test_metrics.py
│   │   └── integration/
│   │       └── test_pipeline_e2e.py
│   ├── jobs/                          # Reference YAMLs (not deployed directly)
│   └── sql/
│       ├── create_tables.sql
│       └── quality_checks.sql
│
├── backend/
│   └── app/
│       ├── main.py
│       ├── routes/                    # products, competitors, analysis
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
│   ├── dev.sh                         # Dev: DB in Docker, services run locally
│   └── staging.sh                     # Staging: all services in Docker
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
* Hyperparameter tuning with Hyperopt or Optuna

---

## Author

**Pranav Chourasia** — Data Engineer | AI/ML Enthusiast
