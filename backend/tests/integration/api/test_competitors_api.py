import pytest

from backend.app.routes import competitors as competitors_route
from backend.app.services.product_exceptions import (
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
)

pytestmark = [pytest.mark.integration, pytest.mark.api]

_PARENT_ASIN = "B07PARENT01"

_COMPETITOR_LIST = [
    {
        "asin": "B00COMP0001",
        "title": "Competitor A",
        "url": "https://amazon.com/dp/B00COMP0001",
        "brand": "BrandA",
        "price": 24.99,
        "currency": "USD",
        "rating": 4.2,
        "images": ["https://img-a.jpg"],
        "amazon_domain": "amazon.com",
    },
]


class TestGetCompetitorsEndpoint:
    def test_returns_competitors_list(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route, "get_competitors", lambda parent_asin, repo: _COMPETITOR_LIST
        )

        response = client.get(f"/api/competitors?parent_asin={_PARENT_ASIN}")

        assert response.status_code == 200
        body = response.json()
        assert "competitors" in body
        assert len(body["competitors"]) == 1
        assert body["competitors"][0]["asin"] == "B00COMP0001"

    def test_returns_empty_list_when_no_competitors(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route, "get_competitors", lambda parent_asin, repo: []
        )

        response = client.get(f"/api/competitors?parent_asin={_PARENT_ASIN}")

        assert response.status_code == 200
        assert response.json() == {"competitors": []}

    def test_missing_parent_asin_returns_422(self, client):
        response = client.get("/api/competitors")

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"

    def test_response_includes_request_id_header(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route, "get_competitors", lambda parent_asin, repo: []
        )

        response = client.get(
            f"/api/competitors?parent_asin={_PARENT_ASIN}",
            headers={"X-Request-ID": "get-competitors-id"},
        )

        assert response.headers["X-Request-ID"] == "get-competitors-id"

    def test_competitor_fields_are_validated_by_response_model(self, monkeypatch, client):
        raw = [{**_COMPETITOR_LIST[0], "unknown_extra_field": "should be stripped"}]
        monkeypatch.setattr(
            competitors_route, "get_competitors", lambda parent_asin, repo: raw
        )

        response = client.get(f"/api/competitors?parent_asin={_PARENT_ASIN}")

        assert response.status_code == 200
        assert "unknown_extra_field" not in response.json()["competitors"][0]


class TestFetchCompetitorsEndpoint:
    def test_fetches_and_returns_competitors(self, monkeypatch, client):
        monkeypatch.setattr(
            competitors_route,
            "fetch_competitors",
            lambda asin, domain, geo_location, repo: _COMPETITOR_LIST,
        )

        response = client.post(
            "/api/competitors/fetch",
            json={"asin": "B07PARENT01", "domain": "com", "geo": "90210"},
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["competitors"]) == 1
        assert body["competitors"][0]["asin"] == "B00COMP0001"

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

        def capture(*args, **kwargs):
            received["asin"] = args[0]
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
            headers={"X-Request-ID": "fetch-competitors-id"},
        )

        assert response.headers["X-Request-ID"] == "fetch-competitors-id"
