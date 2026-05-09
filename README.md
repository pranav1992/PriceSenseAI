# 🚀 PriceSense AI

### Real-Time Product Intelligence & Competitor Analysis Platform

---

## 📌 Overview

**PriceSense AI** is a production-grade data platform that ingests product data from external sources (Oxylabs), processes it using a **Medallion Architecture (Bronze → Silver → Gold)** on Databricks, and provides **AI-powered insights and analytics** using LLMs.

The system enables **real-time competitor analysis, price tracking, and intelligent decision-making** for e-commerce products.

---

## 🧠 Key Features

* 📡 Data ingestion from Oxylabs APIs
* 🏗️ Medallion Architecture (Delta Lake)
* 🔄 Scalable data pipelines (Databricks + Spark)
* 📊 Time-series price tracking & forecasting
* 🤖 LLM-based product analysis & insights
* 📉 Competitor price monitoring
* 🚨 Alerting system (price drops, anomalies)
* 📈 Analytics dashboards

---

## 🏗️ Architecture

```text
Oxylabs API
     ↓
Ingestion Layer
     ↓
Bronze Layer (Raw Data)
     ↓
Silver Layer (Cleaned & Structured)
     ↓
Gold Layer (Business Insights)
     ↓
LLM Analyzer + API Layer
     ↓
Dashboard / Client
```

---

## 🧱 Tech Stack

* **Data Ingestion:** Oxylabs API
* **Processing:** Apache Spark (Databricks)
* **Storage:** Delta Lake
* **Orchestration:** Airflow / Databricks Workflows
* **Backend API:** FastAPI
* **LLM Layer:** OpenAI / Local LLM + Vector DB
* **Visualization:** Power BI / Databricks SQL

---

## 📊 Data Model

### Bronze Layer

* Raw product data
* Raw price snapshots
* Raw reviews

### Silver Layer

* Cleaned products
* Normalized pricing
* Deduplicated records
* Competitor mapping

### Gold Layer

* Competitor price comparison
* Price trends & features
* Product insights
* Forecasting outputs

---

## 🔍 Use Cases

* 📉 Track competitor price changes
* 📦 Monitor product demand trends
* 🧠 Generate AI-driven product insights
* 🚨 Detect anomalies in pricing or availability
* 📊 Build dashboards for decision-making

---

## 🤖 LLM Capabilities

* Product comparison summaries
* Price trend explanations
* Market insights generation
* Conversational analytics (chat interface)

---

## ⚙️ Setup

### 1. Clone repo

```bash
git clone https://github.com/pranav1992/PriceSenseAI.git
cd PriceSenseAI
```

---

### 2. Install dependencies

```bash
uv sync
```

---

### 3. Configure environment

Create a `.env` file in the project root:

```bash
OXYLABS_USERNAME=your_username
OXYLABS_PASSWORD=your_password
OXYLABS_API_URL=https://realtime.oxylabs.io/v1/queries
```

---

### 4. Run the application

#### Dev — DB in Docker, backend & frontend run locally

Frontend and backend run with hot reload. Only the database runs in Docker.

```bash
./scripts/dev.sh
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| Database | localhost:5432 (Docker) |

Press **Ctrl+C** to stop. The database container keeps running so your data is preserved between sessions. To stop it manually:

```bash
docker compose stop db
```

#### Staging — all services in Docker

Mirrors a production-like environment with all three services containerised.

```bash
./scripts/staging.sh
```

To run in detached mode:

```bash
./scripts/staging.sh -d
```

To stop:

```bash
docker compose down
```

---

### 5. Run ingestion

```bash
uv run python ingestion/jobs/ingest_products.py
```

---

### 6. Run pipeline (Databricks)

```bash
uv run databricks bundle deploy
```

---

## 🧪 Testing

```bash
cd backend && uv run pytest
```

Run only unit or integration tests:

```bash
uv run pytest -m unit
uv run pytest -m integration
```

---

## 📁 Project Structure

```text
PriceSenseAI/
│
├── README.md
├── .env.example
├── pyproject.toml
├── requirements.txt
├── docker-compose.yml
│
├── configs/
│   ├── dev.yml
│   ├── prod.yml
│   └── sources.yml
│
├── ingestion/
│   ├── oxylabs_client/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── schemas.py
│   │   └── exceptions.py
│   │
│   ├── jobs/
│   │   ├── ingest_products.py
│   │   ├── ingest_prices.py
│   │   └── ingest_reviews.py
│   │
│   └── tests/
│
├── databricks/
│   ├── notebooks/
│   │   ├── 01_bronze_ingestion.py
│   │   ├── 02_silver_cleaning.py
│   │   ├── 03_gold_analytics.py
│   │   └── 04_forecasting.py
│   │
│   ├── jobs/
│   │   ├── bronze_job.yml
│   │   ├── silver_job.yml
│   │   └── gold_job.yml
│   │
│   ├── sql/
│   │   ├── create_tables.sql
│   │   ├── gold_views.sql
│   │   └── quality_checks.sql
│   │
│   └── databricks.yml
│
├── pipelines/
│   ├── bronze/
│   │   ├── load_raw_products.py
│   │   └── load_raw_prices.py
│   │
│   ├── silver/
│   │   ├── clean_products.py
│   │   ├── normalize_prices.py
│   │   ├── deduplicate.py
│   │   └── product_matching.py
│   │
│   └── gold/
│       ├── competitor_summary.py
│       ├── price_history_features.py
│       ├── product_rankings.py
│       └── anomaly_detection.py
│
|
├── llm_analyzer/
│   ├── __init__.py
│   ├── prompts/
│   │   ├── product_analysis.md
│   │   ├── competitor_summary.md
│   │   └── price_recommendation.md
│   │
│   ├── retriever.py
│   ├── analyzer.py
│   ├── embeddings.py
│   ├── vector_store.py
│   └── tools.py
│
|
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── products/
│   │   │   │   └── page.tsx
│   │   │   ├── competitors/
│   │   │   │   └── page.tsx
│   │   │   ├── analytics/
│   │   │   │   └── page.tsx
│   │   │   └── chat/
│   │   │       └── page.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── ProductCard.tsx
│   │   │   ├── PriceChart.tsx
│   │   │   ├── CompetitorTable.tsx
│   │   │   ├── InsightCard.tsx
│   │   │   └── ChatBox.tsx
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   └── types.ts
│   │   │
│   │   └── styles/
│   │       └── globals.css
├── backend/
│   ├── main.py
│   ├── routes/
│   │   ├── products.py
│   │   ├── competitors.py
│   │   ├── analytics.py
│   │   └── chat.py
│   ├── services/
│   │   ├── product_service.py
│   │   ├── analytics_service.py
│   │   └── llm_service.py
│   └── schemas/
│       ├── product.py
│       └── response.py
│
├── orchestration/
│   ├── airflow/
│   │   ├── dags/
│   │   │   └── product_pipeline_dag.py
│   │   └── plugins/
│   │
│   └── databricks_workflows/
│       └── product_intelligence_workflow.yml
│
├── data_quality/
│   ├── expectations/
│   │   ├── bronze_expectations.yml
│   │   ├── silver_expectations.yml
│   │   └── gold_expectations.yml
│   │
│   └── checks.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── data_quality/
│
├── scripts/
│   ├── dev.sh             # Dev: DB in Docker, backend + frontend run locally
│   ├── staging.sh         # Staging: all services in Docker
│   └── run_backend.sh     # Run backend standalone
│
└── docs/
    ├── architecture.md
    ├── data_model.md
    ├── pipeline_flow.md
    └── api_docs.md
```

---

## 🚀 Future Improvements

* Real-time streaming (Kafka)
* Advanced forecasting (Deep Learning)
* Reinforcement learning for pricing
* Multi-marketplace expansion

---

## 👨‍💻 Author

**Pranav Chourasia**
Data Engineer | AI/ML Enthusiast

---

## ⭐ If you like this project

Give it a star ⭐ on GitHub!
