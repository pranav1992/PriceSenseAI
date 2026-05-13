FEATURE_COLS = [
    "current_price",
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
]

ENGINEERED_COLS = ["day_of_week", "price_to_median_ratio"]

ALL_FEATURE_COLS = FEATURE_COLS + ENGINEERED_COLS

TARGET_COL = "suggested_price"

ROLLING_WINDOW_DAYS = 7
RATING_PREMIUM_THRESHOLD = 0.3
RATING_PREMIUM_PCT = 0.03
PRICE_POSITION_BAND = 0.05
