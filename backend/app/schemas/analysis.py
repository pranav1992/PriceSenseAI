from pydantic import BaseModel


class PriceStats(BaseModel):
    median: float
    avg: float
    min: float
    max: float
    count: int


class PriceSuggestion(BaseModel):
    suggested_price: float
    discount_pct: float
    price_position: str  # "above_market" | "at_market" | "below_market"


class StockSignal(BaseModel):
    level: str  # "in_stock" | "low_stock" | "out_of_stock" | "unknown"
    severity: str  # "ok" | "warning" | "critical" | "info"
    action: str | None = None


class AnalysisResponse(BaseModel):
    asin: str
    current_price: float | None
    price_stats: PriceStats | None
    suggestion: PriceSuggestion | None
    stock_signal: StockSignal


class InsightsResponse(BaseModel):
    asin: str
    price_analysis: str
    discount_recommendation: str
    competitive_positioning: str
