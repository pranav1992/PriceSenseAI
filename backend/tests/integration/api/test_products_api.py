import logging

import pytest

from backend.app.routes import products as products_route

pytestmark = [pytest.mark.integration, pytest.mark.api]


def test_health_endpoint_returns_request_id(client):
    response = client.get("/", headers={"X-Request-ID": "health-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "health-request-id"
    assert response.json() == {"message": "Hello World"}


def test_health_endpoint_generates_request_id(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.json() == {"message": "Hello World"}


def test_health_endpoint_writes_access_log(client, caplog):
    with caplog.at_level(logging.INFO, logger="backend.access"):
        response = client.get("/", headers={"X-Request-ID": "access-request-id"})

    assert response.status_code == 200

    access_record = next(
        record
        for record in caplog.records
        if record.name == "backend.access"
        and getattr(record, "request_id", None) == "access-request-id"
    )
    assert access_record.method == "GET"
    assert access_record.path == "/"
    assert access_record.status_code == 200
    assert isinstance(access_record.duration_ms, float)


def test_scrape_product_endpoint_returns_product(
    monkeypatch, client, scrape_request, scraped_product
):
    def scrape_product(asin, geo_location):
        assert asin == scrape_request["asin"]
        assert geo_location == scrape_request["geo_location"]
        return scraped_product

    monkeypatch.setattr(products_route, "scrape_product", scrape_product)

    response = client.post(
        "/api/products/scrape",
        json=scrape_request,
        headers={"X-Request-ID": "scrape-request-id"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "scrape-request-id"
    assert response.json() == {"product": scraped_product}
