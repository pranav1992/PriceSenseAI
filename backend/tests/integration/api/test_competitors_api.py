import pytest

from backend.app.routes import competitors as competitors_route
from backend.app.services.product_exceptions import (
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
)

pytestmark = [pytest.mark.integration, pytest.mark.api]

_PARENT_ASIN = "B07PARENT01"

_CACHED_COMPETITORS = [
    {
        "asin": "B00COMP0001",
        "title": "Cached Competitor",
        "url": "https://amazon.com/dp/B00COMP0001",
        "brand": "BrandA",
        "price": 24.99,
        "currency": "USD",
        "rating": 4.2,
        "images": [],
        "amazon_domain": "amazon.com",
    }
]

_SCRAPED_COMPETITORS = [
    {
        "asin": "B00COMP0002",
        "title": "Scraped Competitor",
        "url": "https://amazon.com/dp/B00COMP0002",
        "brand": "BrandB",
        "price": 19.99,
        "currency": "USD",
        "rating": 3.8,
        "images": [],
        "amazon_domain": "amazon.com",
    }
]


class TestGetCompetitorsEndpoint:
    """GET /api/competitors — pure DB cache read, never scrapes."""

    def test_returns_cached_competitors(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route,
            "get_competitors",
            lambda parent_asin, repo: _CACHED_COMPETITORS,
        )

        response = client.get(f"/api/competitors?parent_asin={_PARENT_ASIN}")

        assert response.status_code == 200
        body = response.json()
        assert len(body["competitors"]) == 1
        assert body["competitors"][0]["asin"] == "B00COMP0001"

    def test_returns_empty_when_cache_is_empty(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route, "get_competitors", lambda parent_asin, repo: []
        )

        response = client.get(f"/api/competitors?parent_asin={_PARENT_ASIN}")

        assert response.status_code == 200
        assert response.json() == {"competitors": []}

    def test_missing_parent_asin_returns_422(self, client):
        response = client.get("/api/competitors")

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_response_includes_request_id_header(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route, "get_competitors", lambda parent_asin, repo: []
        )

        response = client.get(
            f"/api/competitors?parent_asin={_PARENT_ASIN}",
            headers={"X-Request-ID": "get-request-id"},
        )

        assert response.headers["X-Request-ID"] == "get-request-id"

    def test_response_model_strips_unknown_fields(self, monkeypatch, client):
        raw = [{**_CACHED_COMPETITORS[0], "internal_field": "should be stripped"}]
        monkeypatch.setattr(
            competitors_route, "get_competitors", lambda parent_asin, repo: raw
        )

        response = client.get(f"/api/competitors?parent_asin={_PARENT_ASIN}")

        assert "internal_field" not in response.json()["competitors"][0]


class TestFetchCompetitorsEndpoint:
    """POST /api/competitors/fetch — DB-first: returns cached if available, scrapes on miss."""

    def test_returns_cached_competitors_without_scraping(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route,
            "fetch_competitors",
            lambda asin, domain, geo_location, repo: _CACHED_COMPETITORS,
        )

        response = client.post(
            "/api/competitors/fetch",
            json={"asin": "B07PARENT01", "domain": "com", "geo": "90210"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["competitors"][0]["asin"] == "B00COMP0001"
        assert body["competitors"][0]["title"] == "Cached Competitor"

    def test_scrapes_and_returns_on_cache_miss(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route,
            "fetch_competitors",
            lambda asin, domain, geo_location, repo: _SCRAPED_COMPETITORS,
        )

        response = client.post(
            "/api/competitors/fetch",
            json={"asin": "B07PARENT01", "domain": "com", "geo": "90210"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["competitors"][0]["asin"] == "B00COMP0002"
        assert body["competitors"][0]["title"] == "Scraped Competitor"

    def test_returns_empty_list_when_no_competitors_found(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route, "fetch_competitors", lambda *a, **kw: []
        )

        response = client.post(
            "/api/competitors/fetch",
            json={"asin": "B07PARENT01", "domain": "com", "geo": "90210"},
        )

        assert response.status_code == 200
        assert response.json() == {"competitors": []}

    def test_missing_required_fields_returns_422(self, client):
        response = client.post("/api/competitors/fetch", json={})

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        fields = {d["field"] for d in error["details"]}
        assert "body.asin" in fields
        assert "body.domain" in fields
        assert "body.geo" in fields

    def test_provider_error_returns_502(self, monkeypatch, client):
        def raise_provider_error(*args, **kwargs):
            raise ProductScrapeProviderError("upstream failed")

        monkeypatch.setattr(competitors_route, "fetch_competitors", raise_provider_error)

        response = client.post(
            "/api/competitors/fetch",
            json={"asin": "B07PARENT01", "domain": "com", "geo": "90210"},
        )

        assert response.status_code == 502
        assert response.json()["error"]["code"] == "PRODUCT_SCRAPE_PROVIDER_ERROR"

    def test_timeout_error_returns_504(self, monkeypatch, client):
        def raise_timeout(*args, **kwargs):
            raise ProductScrapeTimeoutError()

        monkeypatch.setattr(competitors_route, "fetch_competitors", raise_timeout)

        response = client.post(
            "/api/competitors/fetch",
            json={"asin": "B07PARENT01", "domain": "com", "geo": "90210"},
        )

        assert response.status_code == 504
        assert response.json()["error"]["code"] == "PRODUCT_SCRAPE_TIMEOUT"

    def test_asin_is_normalised_before_reaching_service(self, monkeypatch, client):
        received = {}

        def capture(asin, domain, geo_location, repo):
            received["asin"] = asin
            return []

        monkeypatch.setattr(competitors_route, "fetch_competitors", capture)

        client.post(
            "/api/competitors/fetch",
            json={"asin": "  b07parent01  ", "domain": "com", "geo": "90210"},
        )

        assert received["asin"] == "B07PARENT01"

    def test_response_includes_request_id_header(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route, "fetch_competitors", lambda *a, **kw: []
        )

        response = client.post(
            "/api/competitors/fetch",
            json={"asin": "B07PARENT01", "domain": "com", "geo": "90210"},
            headers={"X-Request-ID": "fetch-request-id"},
        )

        assert response.headers["X-Request-ID"] == "fetch-request-id"
