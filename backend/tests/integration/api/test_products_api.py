import logging

import pytest

from backend.app.routes import products as products_route

pytestmark = [pytest.mark.integration, pytest.mark.api]


class TestHealthEndpoint:
    def test_returns_ok_with_request_id(self, client):
        response = client.get("/health", headers={"X-Request-ID": "health-request-id"})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "health-request-id"
        assert response.json() == {"status": "ok"}

    def test_generates_request_id_when_not_provided(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers["X-Request-ID"]

    def test_writes_access_log_entry(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="backend.access"):
            response = client.get(
                "/health", headers={"X-Request-ID": "access-request-id"}
            )

        assert response.status_code == 200

        access_record = next(
            record
            for record in caplog.records
            if record.name == "backend.access"
            and getattr(record, "request_id", None) == "access-request-id"
        )
        assert access_record.method == "GET"
        assert access_record.path == "/health"
        assert access_record.status_code == 200
        assert isinstance(access_record.duration_ms, float)


class TestScrapeProductEndpoint:
    def test_returns_product_in_response_envelope(
        self, monkeypatch, client, scrape_request, scraped_product
    ):
        def scrape_product(asin, geo_location, domain, repo):
            assert asin == scraped_product["asin"]
            assert geo_location == scraped_product["geo_location"]
            return scraped_product

        monkeypatch.setattr(products_route, "scrape_product", scrape_product)

        response = client.post(
            "/api/products/scrape",
            json=scrape_request,
            headers={"X-Request-ID": "scrape-request-id"},
        )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "scrape-request-id"
        body = response.json()
        assert body["product"]["asin"] == scraped_product["asin"]
        assert body["product"]["title"] == scraped_product["title"]
        assert body["product"]["price"] == scraped_product["price"]
        assert body["product"]["currency"] == scraped_product["currency"]

    def test_response_model_strips_unknown_fields(self, monkeypatch, client, scrape_request):
        def scrape_product(*args, **kwargs):
            return {"asin": "B07FZ8S74R", "unknown_field": "should be stripped"}

        monkeypatch.setattr(products_route, "scrape_product", scrape_product)

        response = client.post("/api/products/scrape", json=scrape_request)

        assert response.status_code == 200
        assert "unknown_field" not in response.json()["product"]

    def test_response_includes_default_list_fields(self, monkeypatch, client, scrape_request):
        def scrape_product(*args, **kwargs):
            return {"asin": "B07FZ8S74R", "title": "Minimal product"}

        monkeypatch.setattr(products_route, "scrape_product", scrape_product)

        response = client.post("/api/products/scrape", json=scrape_request)

        product = response.json()["product"]
        assert product["images"] == []
        assert product["categories"] == []
        assert product["category_path"] == []
        assert product["buybox"] == []
        assert product["product_overview"] == []

    def test_asin_is_uppercased_by_request_validator(self, monkeypatch, client):
        received = {}

        def scrape_product(asin, geo_location, domain, repo):
            received["asin"] = asin
            return {"asin": asin}

        monkeypatch.setattr(products_route, "scrape_product", scrape_product)

        client.post(
            "/api/products/scrape",
            json={"asin": "b07fz8s74r", "geo_location": "90210"},
        )

        assert received["asin"] == "B07FZ8S74R"
