import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def client_no_raise():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def scrape_request():
    return {"asin": "B07FZ8S74R", "geo_location": "90210"}


@pytest.fixture
def scraped_product(scrape_request):
    return {
        "asin": scrape_request["asin"],
        "geo_location": scrape_request["geo_location"],
        "title": "Test product",
        "price": 19.99,
        "currency": "USD",
    }
