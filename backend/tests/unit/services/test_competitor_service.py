from unittest.mock import MagicMock

import pytest
import requests

from backend.app.services import competitors as competitors_module
from backend.app.services.competitors import fetch_competitors, get_competitors
from backend.app.services.product_exceptions import (
    ProductScrapeConfigurationError,
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
    ProductScrapeUnavailableError,
)

pytestmark = pytest.mark.unit

_PARENT_ASIN = "B07PARENT01"

_RAW_RESULTS = [
    {"asin": "B00COMP0001", "title": "Competitor A", "price": 24.99},
    {"asin": "B00COMP0002", "title": "Competitor B", "price": 19.99},
]


def _make_repo():
    return MagicMock()


class TestGetCompetitors:
    def test_returns_serialized_rows_from_repo(self):
        mock_row_a = MagicMock()
        mock_row_a.to_dict.return_value = {"asin": "B00COMP0001", "title": "Competitor A"}
        mock_row_b = MagicMock()
        mock_row_b.to_dict.return_value = {"asin": "B00COMP0002", "title": "Competitor B"}

        repo = _make_repo()
        repo.get_by_parent_asin.return_value = [mock_row_a, mock_row_b]

        result = get_competitors(_PARENT_ASIN, repo)

        assert result == [
            {"asin": "B00COMP0001", "title": "Competitor A"},
            {"asin": "B00COMP0002", "title": "Competitor B"},
        ]
        repo.get_by_parent_asin.assert_called_once_with(_PARENT_ASIN)

    def test_returns_empty_list_when_no_competitors(self):
        repo = _make_repo()
        repo.get_by_parent_asin.return_value = []

        result = get_competitors(_PARENT_ASIN, repo)

        assert result == []


class TestFetchCompetitors:
    def test_returns_scraped_results(self, monkeypatch):
        monkeypatch.setattr(
            competitors_module, "scrape_competitors", lambda *a, **kw: _RAW_RESULTS
        )
        repo = _make_repo()

        result = fetch_competitors(_PARENT_ASIN, "com", "90210", repo)

        assert result == _RAW_RESULTS

    def test_saves_results_via_repo(self, monkeypatch):
        monkeypatch.setattr(
            competitors_module, "scrape_competitors", lambda *a, **kw: _RAW_RESULTS
        )
        repo = _make_repo()

        fetch_competitors(_PARENT_ASIN, "com", "90210", repo)

        repo.replace_for_parent.assert_called_once_with(_PARENT_ASIN, _RAW_RESULTS)

    def test_maps_value_error_to_configuration_error(self, monkeypatch):
        def raise_value_error(*args, **kwargs):
            raise ValueError("missing credentials")

        monkeypatch.setattr(competitors_module, "scrape_competitors", raise_value_error)

        with pytest.raises(ProductScrapeConfigurationError):
            fetch_competitors(_PARENT_ASIN, "com", "90210", _make_repo())

    def test_maps_timeout_to_timeout_error(self, monkeypatch):
        def raise_timeout(*args, **kwargs):
            raise requests.Timeout("timed out")

        monkeypatch.setattr(competitors_module, "scrape_competitors", raise_timeout)

        with pytest.raises(ProductScrapeTimeoutError):
            fetch_competitors(_PARENT_ASIN, "com", "90210", _make_repo())

    def test_maps_http_error_to_provider_error_with_status(self, monkeypatch):
        response = requests.Response()
        response.status_code = 503

        def raise_http_error(*args, **kwargs):
            raise requests.HTTPError("service unavailable", response=response)

        monkeypatch.setattr(competitors_module, "scrape_competitors", raise_http_error)

        with pytest.raises(ProductScrapeProviderError) as exc_info:
            fetch_competitors(_PARENT_ASIN, "com", "90210", _make_repo())

        assert exc_info.value.details == {"upstream_status_code": 503}

    def test_maps_http_error_without_response_to_provider_error(self, monkeypatch):
        def raise_http_error(*args, **kwargs):
            raise requests.HTTPError("error", response=None)

        monkeypatch.setattr(competitors_module, "scrape_competitors", raise_http_error)

        with pytest.raises(ProductScrapeProviderError) as exc_info:
            fetch_competitors(_PARENT_ASIN, "com", "90210", _make_repo())

        assert exc_info.value.details == {"upstream_status_code": None}

    def test_maps_connection_error_to_unavailable_error(self, monkeypatch):
        def raise_connection_error(*args, **kwargs):
            raise requests.ConnectionError("no route to host")

        monkeypatch.setattr(competitors_module, "scrape_competitors", raise_connection_error)

        with pytest.raises(ProductScrapeUnavailableError):
            fetch_competitors(_PARENT_ASIN, "com", "90210", _make_repo())

    def test_does_not_save_when_scrape_fails(self, monkeypatch):
        monkeypatch.setattr(
            competitors_module,
            "scrape_competitors",
            lambda *a, **kw: (_ for _ in ()).throw(requests.Timeout()),
        )
        repo = _make_repo()

        with pytest.raises(ProductScrapeTimeoutError):
            fetch_competitors(_PARENT_ASIN, "com", "90210", repo)

        repo.replace_for_parent.assert_not_called()
