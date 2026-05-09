from unittest.mock import MagicMock

import pytest

from backend.app.schemas.analysis import PriceStats
from backend.app.services.analysis import (
    compute_price_stats,
    compute_price_suggestion,
    compute_stock_signal,
)

pytestmark = pytest.mark.unit


def _competitor(price=None, rating=None):
    c = MagicMock()
    c.price = price
    c.rating = rating
    return c


def _stats(median=100.0, avg=100.0, min_=80.0, max_=120.0, count=5):
    return PriceStats(median=median, avg=avg, min=min_, max=max_, count=count)


# ── compute_price_stats ───────────────────────────────────────────────────────

class TestComputePriceStats:
    def test_returns_none_for_empty_list(self):
        assert compute_price_stats([]) is None

    def test_returns_none_when_all_prices_are_null(self):
        assert compute_price_stats([_competitor(price=None), _competitor(price=None)]) is None

    def test_calculates_median_avg_min_max(self):
        stats = compute_price_stats([_competitor(10.0), _competitor(20.0), _competitor(30.0)])
        assert stats.median == 20.0
        assert stats.avg == 20.0
        assert stats.min == 10.0
        assert stats.max == 30.0

    def test_count_reflects_only_non_null_prices(self):
        stats = compute_price_stats([
            _competitor(10.0), _competitor(None), _competitor(30.0)
        ])
        assert stats.count == 2

    def test_single_competitor(self):
        stats = compute_price_stats([_competitor(49.99)])
        assert stats.median == 49.99
        assert stats.count == 1

    def test_even_number_of_prices_uses_middle_average_for_median(self):
        # median of [10, 20] = 15
        stats = compute_price_stats([_competitor(10.0), _competitor(20.0)])
        assert stats.median == 15.0


# ── compute_price_suggestion ──────────────────────────────────────────────────

class TestComputePriceSuggestion:
    def test_above_market_when_price_more_than_5pct_above_median(self):
        result = compute_price_suggestion(110.0, _stats(median=100.0), None, [])
        assert result.price_position == "above_market"

    def test_at_market_when_price_is_equal_to_median(self):
        result = compute_price_suggestion(100.0, _stats(median=100.0), None, [])
        assert result.price_position == "at_market"

    def test_at_market_within_5pct_band(self):
        result = compute_price_suggestion(104.0, _stats(median=100.0), None, [])
        assert result.price_position == "at_market"

    def test_below_market_when_price_more_than_5pct_below_median(self):
        result = compute_price_suggestion(80.0, _stats(median=100.0), None, [])
        assert result.price_position == "below_market"

    def test_discount_pct_positive_when_above_market(self):
        result = compute_price_suggestion(120.0, _stats(median=100.0), None, [])
        assert result.discount_pct > 0

    def test_discount_pct_zero_when_at_or_below_market(self):
        result = compute_price_suggestion(80.0, _stats(median=100.0), None, [])
        assert result.discount_pct == 0.0

    def test_rating_premium_applied_when_product_rates_higher_than_average(self):
        # Product rating 4.8 vs competitor avg 4.0 → 3% premium on suggested price
        without_premium = compute_price_suggestion(200.0, _stats(median=100.0), None, [])
        with_premium = compute_price_suggestion(200.0, _stats(median=100.0), 4.8, [4.0, 4.0, 4.0])
        assert with_premium.suggested_price > without_premium.suggested_price

    def test_no_rating_premium_when_product_rating_is_not_significantly_higher(self):
        # Product rating 4.2 vs competitor avg 4.0 (diff < 0.3) → no premium
        without_premium = compute_price_suggestion(200.0, _stats(median=100.0), None, [])
        same_premium = compute_price_suggestion(200.0, _stats(median=100.0), 4.2, [4.0, 4.0, 4.0])
        assert same_premium.suggested_price == without_premium.suggested_price

    def test_suggested_price_rounded_to_two_decimal_places(self):
        result = compute_price_suggestion(100.0, _stats(median=33.333), None, [])
        assert result.suggested_price == round(result.suggested_price, 2)


# ── compute_stock_signal ──────────────────────────────────────────────────────

class TestComputeStockSignal:
    def test_in_stock_string(self):
        signal = compute_stock_signal("In Stock")
        assert signal.level == "in_stock"
        assert signal.severity == "ok"
        assert signal.action is None

    def test_available_string(self):
        signal = compute_stock_signal("Usually ships within 24 hours, available now")
        assert signal.level == "in_stock"

    def test_out_of_stock_string(self):
        signal = compute_stock_signal("Out of Stock")
        assert signal.level == "out_of_stock"
        assert signal.severity == "critical"
        assert signal.action is not None

    def test_none_treated_as_out_of_stock(self):
        assert compute_stock_signal(None).level == "out_of_stock"

    def test_empty_string_treated_as_out_of_stock(self):
        assert compute_stock_signal("").level == "out_of_stock"

    def test_limited_phrasing(self):
        signal = compute_stock_signal("Only 3 left in stock – order soon")
        assert signal.level == "low_stock"
        assert signal.severity == "warning"
        assert signal.action is not None

    def test_few_phrasing(self):
        assert compute_stock_signal("Very few remaining").level == "low_stock"

    def test_unknown_status(self):
        signal = compute_stock_signal("Ships in 3-5 business days")
        assert signal.level == "unknown"
        assert signal.severity == "info"
        assert signal.action is not None

    def test_case_insensitive_matching(self):
        assert compute_stock_signal("OUT OF STOCK").level == "out_of_stock"
        assert compute_stock_signal("IN STOCK").level == "in_stock"
