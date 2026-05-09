from unittest.mock import MagicMock

import pytest
import requests

from backend.app.services import products
from backend.app.services.product_exceptions import (
    ProductScrapeConfigurationError,
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
    ProductScrapeUnavailableError,
)

pytestmark = pytest.mark.unit


def test_scrape_product_returns_scraped_product(monkeypatch, scraped_product):
    def scrape_product_details(asin, geo_location, domain):
        assert asin == scraped_product["asin"]
        assert geo_location == scraped_product["geo_location"]
        return scraped_product

    monkeypatch.setattr(products, "scrape_product_details", scrape_product_details)

    assert products.scrape_product("B07FZ8S74R", "90210") == scraped_product


def test_scrape_product_maps_configuration_error(monkeypatch):
    def scrape_product_details(*args, **kwargs):
        raise ValueError("missing credentials")

    monkeypatch.setattr(products, "scrape_product_details", scrape_product_details)

    with pytest.raises(ProductScrapeConfigurationError):
        products.scrape_product("B07FZ8S74R", "90210")


def test_scrape_product_maps_timeout_error(monkeypatch):
    def scrape_product_details(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(products, "scrape_product_details", scrape_product_details)

    with pytest.raises(ProductScrapeTimeoutError):
        products.scrape_product("B07FZ8S74R", "90210")


def test_scrape_product_maps_http_error_with_status_detail(monkeypatch):
    response = requests.Response()
    response.status_code = 429

    def scrape_product_details(*args, **kwargs):
        raise requests.HTTPError("rate limited", response=response)

    monkeypatch.setattr(products, "scrape_product_details", scrape_product_details)

    with pytest.raises(ProductScrapeProviderError) as exc_info:
        products.scrape_product("B07FZ8S74R", "90210")

    assert exc_info.value.details == {"upstream_status_code": 429}


def test_scrape_product_maps_request_exception(monkeypatch):
    def scrape_product_details(*args, **kwargs):
        raise requests.ConnectionError("connection failed")

    monkeypatch.setattr(products, "scrape_product_details", scrape_product_details)

    with pytest.raises(ProductScrapeUnavailableError):
        products.scrape_product("B07FZ8S74R", "90210")


def test_scrape_product_calls_repo_upsert_when_provided(monkeypatch, scraped_product):
    monkeypatch.setattr(
        products, "scrape_product_details", lambda *a, **kw: scraped_product
    )
    repo = MagicMock()

    products.scrape_product("B07FZ8S74R", "90210", repo=repo)

    repo.upsert.assert_called_once_with(scraped_product)


def test_scrape_product_skips_upsert_when_repo_is_none(monkeypatch, scraped_product):
    monkeypatch.setattr(
        products, "scrape_product_details", lambda *a, **kw: scraped_product
    )

    result = products.scrape_product("B07FZ8S74R", "90210", repo=None)

    assert result == scraped_product
