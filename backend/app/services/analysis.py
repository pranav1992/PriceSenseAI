import statistics

from ..models.competitor import Competitor
from ..schemas.analysis import PriceStats, PriceSuggestion, StockSignal


def compute_price_stats(competitors: list[Competitor]) -> PriceStats | None:
    prices = [c.price for c in competitors if c.price is not None]
    if not prices:
        return None
    return PriceStats(
        median=round(statistics.median(prices), 2),
        avg=round(statistics.mean(prices), 2),
        min=round(min(prices), 2),
        max=round(max(prices), 2),
        count=len(prices),
    )


def compute_price_suggestion(
    product_price: float,
    stats: PriceStats,
    product_rating: float | None,
    competitor_ratings: list[float],
) -> PriceSuggestion:
    suggested = stats.median

    # Allow a small premium when the product rates meaningfully higher than competitors
    if product_rating and competitor_ratings:
        avg_rating = statistics.mean(competitor_ratings)
        if product_rating > avg_rating + 0.3:
            suggested *= 1.03

    suggested = round(suggested, 2)
    discount_pct = max(0.0, round((product_price - suggested) / product_price * 100, 1))

    if product_price > stats.median * 1.05:
        position = "above_market"
    elif product_price < stats.median * 0.95:
        position = "below_market"
    else:
        position = "at_market"

    return PriceSuggestion(
        suggested_price=suggested,
        discount_pct=discount_pct,
        price_position=position,
    )


def compute_stock_signal(stock_str: str | None) -> StockSignal:
    s = (stock_str or "").lower().strip()
    if not s or "out of stock" in s or s in ("none", "unavailable"):
        return StockSignal(
            level="out_of_stock",
            severity="critical",
            action="Restock immediately — product is unavailable.",
        )
    if "limited" in s or "only" in s or "few" in s:
        return StockSignal(
            level="low_stock",
            severity="warning",
            action="Consider restocking soon.",
        )
    if "in stock" in s or "available" in s:
        return StockSignal(level="in_stock", severity="ok", action=None)
    return StockSignal(level="unknown", severity="info", action="Verify stock status manually.")
