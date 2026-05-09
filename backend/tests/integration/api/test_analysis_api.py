import pytest
from fastapi import HTTPException

from backend.app.routes import analysis as analysis_route
from backend.app.schemas.analysis import AnalysisResponse, InsightsResponse, PriceStats, PriceSuggestion, StockSignal

pytestmark = [pytest.mark.integration, pytest.mark.api]

_ASIN = "B0TESTANALYS"

_STOCK_SIGNAL = StockSignal(level="in_stock", severity="ok", action=None)

_ANALYSIS = AnalysisResponse(
    asin=_ASIN,
    current_price=99.99,
    price_stats=PriceStats(median=89.99, avg=92.0, min=79.99, max=109.99, count=10),
    suggestion=PriceSuggestion(
        suggested_price=89.99, discount_pct=10.0, price_position="above_market"
    ),
    stock_signal=_STOCK_SIGNAL,
)

_INSIGHTS = InsightsResponse(
    asin=_ASIN,
    price_analysis="You are 11% above the market median.",
    discount_recommendation="Reduce by 10% to $89.99 to match the median.",
    competitive_positioning="Position as a reliable mid-range option.",
)


def _build_ok(asin, db):
    return _ANALYSIS, "Test Laptop", "USD"


def _build_not_found(asin, db):
    raise HTTPException(status_code=404, detail=f"Product {asin} not found.")


# ── GET /api/analysis/{asin} ──────────────────────────────────────────────────

class TestGetAnalysisEndpoint:
    def test_returns_200_with_full_analysis(self, monkeypatch, client):
        monkeypatch.setattr(analysis_route, "_build_analysis", _build_ok)
        response = client.get(f"/api/analysis/{_ASIN}")
        assert response.status_code == 200

    def test_response_contains_expected_fields(self, monkeypatch, client):
        monkeypatch.setattr(analysis_route, "_build_analysis", _build_ok)
        body = client.get(f"/api/analysis/{_ASIN}").json()
        assert body["asin"] == _ASIN
        assert body["current_price"] == 99.99
        assert body["price_stats"]["count"] == 10
        assert body["price_stats"]["median"] == 89.99
        assert body["suggestion"]["price_position"] == "above_market"
        assert body["suggestion"]["discount_pct"] == 10.0
        assert body["stock_signal"]["level"] == "in_stock"

    def test_returns_404_when_product_not_scraped(self, monkeypatch, client):
        monkeypatch.setattr(analysis_route, "_build_analysis", _build_not_found)
        response = client.get(f"/api/analysis/{_ASIN}")
        assert response.status_code == 404

    def test_asin_is_uppercased_before_lookup(self, monkeypatch, client):
        received = {}

        def capture(asin, db):
            received["asin"] = asin
            return _ANALYSIS, "Test Laptop", "USD"

        monkeypatch.setattr(analysis_route, "_build_analysis", capture)
        client.get(f"/api/analysis/{_ASIN.lower()}")
        assert received["asin"] == _ASIN

    def test_returns_analysis_with_null_price_stats_when_no_competitors(self, monkeypatch, client):
        no_stats = AnalysisResponse(
            asin=_ASIN,
            current_price=99.99,
            price_stats=None,
            suggestion=None,
            stock_signal=_STOCK_SIGNAL,
        )
        monkeypatch.setattr(
            analysis_route, "_build_analysis", lambda asin, db: (no_stats, "Test", "USD")
        )
        body = client.get(f"/api/analysis/{_ASIN}").json()
        assert body["price_stats"] is None
        assert body["suggestion"] is None

    def test_response_includes_request_id_header(self, monkeypatch, client):
        monkeypatch.setattr(analysis_route, "_build_analysis", _build_ok)
        response = client.get(
            f"/api/analysis/{_ASIN}",
            headers={"X-Request-ID": "analysis-test-id"},
        )
        assert response.headers["X-Request-ID"] == "analysis-test-id"


# ── POST /api/analysis/{asin}/insights ───────────────────────────────────────

class TestGetInsightsEndpoint:
    def test_returns_200_with_insights(self, monkeypatch, client):
        monkeypatch.setattr(analysis_route, "_build_analysis", _build_ok)
        monkeypatch.setattr(analysis_route, "get_ai_insights", lambda *a, **kw: _INSIGHTS)
        response = client.post(f"/api/analysis/{_ASIN}/insights")
        assert response.status_code == 200

    def test_response_contains_narrative_fields(self, monkeypatch, client):
        monkeypatch.setattr(analysis_route, "_build_analysis", _build_ok)
        monkeypatch.setattr(analysis_route, "get_ai_insights", lambda *a, **kw: _INSIGHTS)
        body = client.post(f"/api/analysis/{_ASIN}/insights").json()
        assert body["asin"] == _ASIN
        assert body["price_analysis"] == "You are 11% above the market median."
        assert body["discount_recommendation"] == "Reduce by 10% to $89.99 to match the median."
        assert body["competitive_positioning"] == "Position as a reliable mid-range option."

    def test_returns_404_when_product_not_scraped(self, monkeypatch, client):
        monkeypatch.setattr(analysis_route, "_build_analysis", _build_not_found)
        response = client.post(f"/api/analysis/{_ASIN}/insights")
        assert response.status_code == 404

    def test_asin_is_uppercased_before_lookup(self, monkeypatch, client):
        received = {}

        def capture(asin, db):
            received["asin"] = asin
            return _ANALYSIS, "Test Laptop", "USD"

        monkeypatch.setattr(analysis_route, "_build_analysis", capture)
        monkeypatch.setattr(analysis_route, "get_ai_insights", lambda *a, **kw: _INSIGHTS)
        client.post(f"/api/analysis/{_ASIN.lower()}/insights")
        assert received["asin"] == _ASIN

    def test_passes_correct_args_to_insights_service(self, monkeypatch, client):
        captured = {}

        def capture_insights(asin, title, price, analysis, currency):
            captured.update(asin=asin, title=title, price=price, currency=currency)
            return _INSIGHTS

        monkeypatch.setattr(analysis_route, "_build_analysis", _build_ok)
        monkeypatch.setattr(analysis_route, "get_ai_insights", capture_insights)
        client.post(f"/api/analysis/{_ASIN}/insights")

        assert captured["asin"] == _ASIN
        assert captured["title"] == "Test Laptop"
        assert captured["price"] == 99.99
        assert captured["currency"] == "USD"

    def test_graceful_response_when_llm_unavailable(self, monkeypatch, client):
        degraded = InsightsResponse(
            asin=_ASIN,
            price_analysis="AI insights unavailable — ANTHROPIC_API_KEY is not configured.",
            discount_recommendation="",
            competitive_positioning="",
        )
        monkeypatch.setattr(analysis_route, "_build_analysis", _build_ok)
        monkeypatch.setattr(analysis_route, "get_ai_insights", lambda *a, **kw: degraded)

        response = client.post(f"/api/analysis/{_ASIN}/insights")
        assert response.status_code == 200
        body = response.json()
        assert "unavailable" in body["price_analysis"].lower()

    def test_response_includes_request_id_header(self, monkeypatch, client):
        monkeypatch.setattr(analysis_route, "_build_analysis", _build_ok)
        monkeypatch.setattr(analysis_route, "get_ai_insights", lambda *a, **kw: _INSIGHTS)
        response = client.post(
            f"/api/analysis/{_ASIN}/insights",
            headers={"X-Request-ID": "insights-test-id"},
        )
        assert response.headers["X-Request-ID"] == "insights-test-id"
