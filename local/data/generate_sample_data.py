"""
Generate synthetic but realistic CSV fixtures for local ML development.

Produces three files that mirror the silver and gold Delta table schemas:
  - sample_price_history.csv   ← silver.price_history (own products)
  - sample_competitor_map.csv  ← silver.competitor_map
  - sample_gold_features.csv   ← gold.price_features (rolling features pre-computed)

Run:  uv run python data/generate_sample_data.py
"""

import os
import numpy as np
import pandas as pd
from datetime import date, timedelta

SEED = 42
rng = np.random.default_rng(SEED)

OUT_DIR = os.path.dirname(__file__)

ASINS = ["B0FY52GZFG", "B08N5WRWNW", "B09XYZ1234"]
COMP_ASINS_PER_PRODUCT = {
    "B0FY52GZFG": ["C001", "C002", "C003", "C004", "C005"],
    "B08N5WRWNW": ["C006", "C007", "C008", "C009", "C010"],
    "B09XYZ1234": ["C011", "C012", "C013", "C014", "C015"],
}
BASE_PRICES = {"B0FY52GZFG": 49.99, "B08N5WRWNW": 29.99, "B09XYZ1234": 89.99}
BASE_RATINGS = {"B0FY52GZFG": 4.4, "B08N5WRWNW": 4.1, "B09XYZ1234": 4.7}
DAYS = 90
START_DATE = date(2026, 2, 12)


def date_range(start: date, days: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(days)]


# ── silver.price_history (own products) ──────────────────────────────────────

def make_price_history() -> pd.DataFrame:
    rows = []
    for asin in ASINS:
        base = BASE_PRICES[asin]
        base_rating = BASE_RATINGS[asin]
        price = base
        for d in date_range(START_DATE, DAYS):
            # Random walk with occasional jumps
            price += rng.normal(0, base * 0.005)
            if rng.random() < 0.05:
                price += rng.uniform(-base * 0.08, base * 0.08)
            price = max(price, base * 0.7)

            stock_opts = ["in_stock", "in_stock", "in_stock", "low_stock", "out_of_stock"]
            rows.append({
                "asin":        asin,
                "scrape_date": d.isoformat(),
                "price":       round(price, 2),
                "currency":    "USD",
                "rating":      round(base_rating + rng.normal(0, 0.05), 1),
                "stock":       rng.choice(stock_opts, p=[0.7, 0.15, 0.1, 0.04, 0.01]),
                "source":      "product",
                "parent_asin": None,
            })
    return pd.DataFrame(rows)


# ── silver.competitor_map ─────────────────────────────────────────────────────

def make_competitor_map() -> pd.DataFrame:
    rows = []
    for parent_asin in ASINS:
        base = BASE_PRICES[parent_asin]
        for d in date_range(START_DATE, DAYS):
            comp_asins = COMP_ASINS_PER_PRODUCT[parent_asin]
            comp_prices = sorted(
                [round(base * rng.uniform(0.8, 1.2), 2) for _ in comp_asins]
            )
            for rank, (comp_asin, comp_price) in enumerate(zip(comp_asins, comp_prices), start=1):
                rows.append({
                    "parent_asin":   parent_asin,
                    "asin":          comp_asin,
                    "price":         comp_price,
                    "currency":      "USD",
                    "rating":        round(rng.uniform(3.5, 4.8), 1),
                    "price_diff_pct": round((comp_price - base) / base * 100, 2),
                    "price_rank":    rank,
                    "scrape_date":   d.isoformat(),
                })
    return pd.DataFrame(rows)


# ── gold.price_features (rolling features pre-computed) ──────────────────────

def make_gold_features(price_hist: pd.DataFrame, comp_map: pd.DataFrame) -> pd.DataFrame:
    own = price_hist.copy()
    own["scrape_date"] = pd.to_datetime(own["scrape_date"])
    comp = comp_map.copy()
    comp["scrape_date"] = pd.to_datetime(comp["scrape_date"])

    # Rolling time-series features
    own = own.sort_values(["asin", "scrape_date"])
    own["price_7d_ma"] = (
        own.groupby("asin")["price"]
        .transform(lambda x: x.rolling(7, min_periods=1).mean())
    )
    own["price_7d_volatility"] = (
        own.groupby("asin")["price"]
        .transform(lambda x: x.rolling(7, min_periods=1).std())
    )
    own["price_momentum"] = (
        own.groupby("asin")["price"]
        .transform(lambda x: x.pct_change(7))
    )

    # Competitive aggregates
    comp_agg = (
        comp.groupby(["parent_asin", "scrape_date"])["price"]
        .agg(
            comp_median_price=lambda x: x.median(),
            comp_avg_price="mean",
            comp_min_price="min",
            comp_max_price="max",
            comp_count="count",
        )
        .reset_index()
        .rename(columns={"parent_asin": "asin"})
    )

    gold = own.merge(comp_agg, on=["asin", "scrape_date"], how="left")

    # Competitors below own price
    def count_below(row):
        mask = (
            (comp["parent_asin"] == row["asin"]) &
            (comp["scrape_date"] == row["scrape_date"]) &
            (comp["price"] < row["price"])
        )
        return int(comp[mask].shape[0])

    gold["competitors_below"] = gold.apply(count_below, axis=1)
    gold["comp_pressure_score"] = gold["competitors_below"] / gold["comp_count"].replace(0, np.nan)

    # Rating premium and suggested price
    RATING_PREMIUM_THRESHOLD = 0.3
    RATING_PREMIUM_PCT = 0.03
    comp_avg_rating = (
        comp.groupby(["parent_asin", "scrape_date"])["rating"]
        .mean()
        .reset_index()
        .rename(columns={"parent_asin": "asin", "rating": "comp_avg_rating"})
    )
    gold = gold.merge(comp_avg_rating, on=["asin", "scrape_date"], how="left")

    premium = np.where(
        (gold["rating"] - gold["comp_avg_rating"]) > RATING_PREMIUM_THRESHOLD,
        RATING_PREMIUM_PCT, 0.0
    )
    gold["suggested_price"] = (gold["comp_median_price"] * (1 + premium)).round(2)

    BAND = 0.05
    gold["price_position"] = np.where(
        gold["comp_median_price"].isna(), None,
        np.where(gold["price"] > gold["comp_median_price"] * (1 + BAND), "above_market",
        np.where(gold["price"] < gold["comp_median_price"] * (1 - BAND), "below_market",
                 "at_market"))
    )

    return gold.rename(columns={"price": "current_price"})[[
        "asin", "scrape_date", "current_price", "currency",
        "price_7d_ma", "price_7d_volatility", "price_momentum",
        "comp_median_price", "comp_avg_price", "comp_min_price", "comp_max_price",
        "comp_count", "competitors_below", "comp_pressure_score",
        "suggested_price", "price_position",
    ]]


if __name__ == "__main__":
    print("Generating sample data...")

    price_hist = make_price_history()
    price_hist.to_csv(os.path.join(OUT_DIR, "sample_price_history.csv"), index=False)
    print(f"  sample_price_history.csv  — {len(price_hist):,} rows")

    comp_map = make_competitor_map()
    comp_map.to_csv(os.path.join(OUT_DIR, "sample_competitor_map.csv"), index=False)
    print(f"  sample_competitor_map.csv — {len(comp_map):,} rows")

    gold = make_gold_features(price_hist, comp_map)
    gold.to_csv(os.path.join(OUT_DIR, "sample_gold_features.csv"), index=False)
    print(f"  sample_gold_features.csv  — {len(gold):,} rows")

    print("Done. Load with: pd.read_csv('local/data/sample_gold_features.csv')")
