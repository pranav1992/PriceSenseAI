import requests

from ingestion.oxylabs_client.client import scrape_competitors

from .product_exceptions import (
    ProductScrapeConfigurationError,
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
    ProductScrapeUnavailableError,
)


def get_competitors(parent_asin: str) -> list:
    # No persistent storage yet — always return empty so the caller fetches fresh.
    return []


def fetch_competitors(asin: str, domain: str, geo_location: str) -> list:
    try:
        return scrape_competitors(asin, domain, geo_location)
    except ValueError as exc:
        raise ProductScrapeConfigurationError() from exc
    except requests.Timeout as exc:
        raise ProductScrapeTimeoutError() from exc
    except requests.HTTPError as exc:
        upstream_status_code = exc.response.status_code if exc.response is not None else None
        raise ProductScrapeProviderError(details={"upstream_status_code": upstream_status_code}) from exc
    except requests.RequestException as exc:
        raise ProductScrapeUnavailableError() from exc
