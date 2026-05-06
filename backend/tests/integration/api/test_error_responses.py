import pytest

from backend.app.routes import products as products_route
from backend.app.services.product_exceptions import ProductScrapeProviderError

pytestmark = [pytest.mark.integration, pytest.mark.api]


def test_validation_error_uses_error_envelope(client):
    response = client.post(
        "/api/products/scrape",
        json={},
        headers={"X-Request-ID": "validation-request-id"},
    )

    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "validation-request-id"
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "request_id": "validation-request-id",
            "details": [
                {
                    "field": "body.asin",
                    "message": "Field required",
                    "type": "missing",
                },
                {
                    "field": "body.geo_location",
                    "message": "Field required",
                    "type": "missing",
                },
            ],
        }
    }


def test_application_exception_uses_error_envelope(monkeypatch, client):
    def scrape_product(*args, **kwargs):
        raise ProductScrapeProviderError("Provider failed in test.")

    monkeypatch.setattr(products_route, "scrape_product", scrape_product)

    response = client.post(
        "/api/products/scrape",
        json={"asin": "B07FZ8S74R", "geo_location": "90210"},
        headers={"X-Request-ID": "upstream-request-id"},
    )

    assert response.status_code == 502
    assert response.headers["X-Request-ID"] == "upstream-request-id"
    assert response.json() == {
        "error": {
            "code": "PRODUCT_SCRAPE_PROVIDER_ERROR",
            "message": "Provider failed in test.",
            "request_id": "upstream-request-id",
        }
    }


def test_unhandled_exception_uses_generic_error(monkeypatch, client_no_raise):
    def scrape_product(*args, **kwargs):
        raise RuntimeError("should not leak")

    monkeypatch.setattr(products_route, "scrape_product", scrape_product)

    response = client_no_raise.post(
        "/api/products/scrape",
        json={"asin": "B07FZ8S74R", "geo_location": "90210"},
        headers={"X-Request-ID": "runtime-request-id"},
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "runtime-request-id"
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Internal server error.",
            "request_id": "runtime-request-id",
        }
    }


def test_not_found_uses_error_envelope(client):
    response = client.get(
        "/missing",
        headers={"X-Request-ID": "missing-request-id"},
    )

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "missing-request-id"
    assert response.json() == {
        "error": {
            "code": "HTTP_ERROR",
            "message": "Not Found",
            "request_id": "missing-request-id",
        }
    }
