from unittest.mock import MagicMock

import pytest
import requests

from backend.app.services import competitors as competitors_module
from backend.app.services.competitors import fetch_competitors, get_competitors, refresh_competitors
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


def _make_repo(cached=None):
    repo = MagicMock()
    repo.get_by_parent_asin.return_value = cached or []
    return repo


class TestGetCompetitors:
    def test_returns_serialized_rows_from_repo(self):
        mock_row_a = MagicMock()
        mock_row_a.to_dict.return_value = {"asin": "B00COMP0001", "title": "Competitor A"}
        mock_row_b = MagicMock()
        mock_row_b.to_dict.return_value = {"asin": "B00COMP0002", "title": "Competitor B"}

        repo = _make_repo(cached=[mock_row_a, mock_row_b])

        result = get_competitors(_PARENT_ASIN, repo)

        assert result == [
            {"asin": "B00COMP0001", "title": "Competitor A"},
            {"asin": "B00COMP0002", "title": "Competitor B"},
        ]
        repo.get_by_parent_asin.assert_called_once_with(_PARENT_ASIN)

    def test_returns_empty_list_when_no_competitors(self):
        result = get_competitors(_PARENT_ASIN, _make_repo())
        assert result == []


class TestFetchCompetitors:
    # --- cache-hit path ---

    def test_returns_cached_results_without_scraping(self, monkeypatch):
        mock_row = MagicMock()
        mock_row.to_dict.return_value = {"asin": "B00COMP0001", "title": "Cached Competitor"}
        repo = _make_repo(cached=[mock_row])

        scrape_called = []
        monkeypatch.setattr(
            competitors_module,
            "scrape_competitors",
            lambda *a, **kw: scrape_called.append(True) or [],
        )

        result = fetch_competitors(_PARENT_ASIN, "com", "90210", repo)

        assert result == [{"asin": "B00COMP0001", "title": "Cached Competitor"}]
        assert not scrape_called
        repo.replace_for_parent.assert_not_called()

    def test_cache_hit_returns_all_cached_rows(self, monkeypatch):
        rows = [MagicMock() for _ in range(3)]
        for i, row in enumerate(rows):
            row.to_dict.return_value = {"asin": f"B00COMP000{i}"}
        repo = _make_repo(cached=rows)

        monkeypatch.setattr(
            competitors_module, "scrape_competitors", lambda *a, **kw: []
        )

        result = fetch_competitors(_PARENT_ASIN, "com", "90210", repo)

        assert len(result) == 3

    # --- cache-miss path ---

    def test_scrapes_and_returns_results_on_cache_miss(self, monkeypatch):
        monkeypatch.setattr(
            competitors_module, "scrape_competitors", lambda *a, **kw: _RAW_RESULTS
        )
        repo = _make_repo()

        result = fetch_competitors(_PARENT_ASIN, "com", "90210", repo)

        assert result == _RAW_RESULTS

    def test_saves_scraped_results_to_repo_on_cache_miss(self, monkeypatch):
        monkeypatch.setattr(
            competitors_module, "scrape_competitors", lambda *a, **kw: _RAW_RESULTS
        )
        repo = _make_repo()

        fetch_competitors(_PARENT_ASIN, "com", "90210", repo)

        repo.replace_for_parent.assert_called_once_with(_PARENT_ASIN, _RAW_RESULTS)

    def test_maps_value_error_to_configuration_error(self, monkeypatch):
        monkeypatch.setattr(
            competitors_module,
            "scrape_competitors",
            lambda *a, **kw: (_ for _ in ()).throw(ValueError("missing credentials")),
        )

        with pytest.raises(ProductScrapeConfigurationError):
            fetch_competitors(_PARENT_ASIN, "com", "90210", _make_repo())

    def test_maps_timeout_to_timeout_error(self, monkeypatch):
        monkeypatch.setattr(
            competitors_module,
            "scrape_competitors",
            lambda *a, **kw: (_ for _ in ()).throw(requests.Timeout()),
        )

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
        def raise_timeout(*args, **kwargs):
            raise requests.Timeout()

        monkeypatch.setattr(competitors_module, "scrape_competitors", raise_timeout)
        repo = _make_repo()

        with pytest.raises(ProductScrapeTimeoutError):
            fetch_competitors(_PARENT_ASIN, "com", "90210", repo)

        repo.replace_for_parent.assert_not_called()


class TestRefreshCompetitors:
    def test_always_scrapes_even_when_cache_is_populated(self, monkeypatch):
        rows = [MagicMock()]
        rows[0].to_dict.return_value = {"asin": "B00CACHED001"}
        repo = _make_repo(cached=rows)

        monkeypatch.setattr(
            competitors_module, "scrape_competitors", lambda *a, **kw: _RAW_RESULTS
        )

        result = refresh_competitors(_PARENT_ASIN, "com", "90210", repo)

        assert result == _RAW_RESULTS

    def test_overwrites_db_with_fresh_results(self, monkeypatch):
        repo = _make_repo(cached=[MagicMock()])
        monkeypatch.setattr(
            competitors_module, "scrape_competitors", lambda *a, **kw: _RAW_RESULTS
        )

        refresh_competitors(_PARENT_ASIN, "com", "90210", repo)

        repo.replace_for_parent.assert_called_once_with(_PARENT_ASIN, _RAW_RESULTS)

    def test_does_not_read_from_cache(self, monkeypatch):
        repo = _make_repo()
        monkeypatch.setattr(
            competitors_module, "scrape_competitors", lambda *a, **kw: _RAW_RESULTS
        )

        refresh_competitors(_PARENT_ASIN, "com", "90210", repo)

        repo.get_by_parent_asin.assert_not_called()

    def test_maps_value_error_to_configuration_error(self, monkeypatch):
        monkeypatch.setattr(
            competitors_module,
            "scrape_competitors",
            lambda *a, **kw: (_ for _ in ()).throw(ValueError()),
        )

        with pytest.raises(ProductScrapeConfigurationError):
            refresh_competitors(_PARENT_ASIN, "com", "90210", _make_repo())

    def test_maps_timeout_to_timeout_error(self, monkeypatch):
        monkeypatch.setattr(
            competitors_module,
            "scrape_competitors",
            lambda *a, **kw: (_ for _ in ()).throw(requests.Timeout()),
        )

        with pytest.raises(ProductScrapeTimeoutError):
            refresh_competitors(_PARENT_ASIN, "com", "90210", _make_repo())

    def test_maps_connection_error_to_unavailable_error(self, monkeypatch):
        def raise_connection_error(*args, **kwargs):
            raise requests.ConnectionError()

        monkeypatch.setattr(competitors_module, "scrape_competitors", raise_connection_error)

        with pytest.raises(ProductScrapeUnavailableError):
            refresh_competitors(_PARENT_ASIN, "com", "90210", _make_repo())

    def test_does_not_save_when_scrape_fails(self, monkeypatch):
        def raise_timeout(*args, **kwargs):
            raise requests.Timeout()

        monkeypatch.setattr(competitors_module, "scrape_competitors", raise_timeout)
        repo = _make_repo()

        with pytest.raises(ProductScrapeTimeoutError):
            refresh_competitors(_PARENT_ASIN, "com", "90210", repo)

        repo.replace_for_parent.assert_not_called()
