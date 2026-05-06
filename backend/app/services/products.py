import requests

from ingestion.oxylabs_client.client import scrape_product_details

from .product_exceptions import (
    ProductScrapeConfigurationError,
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
    ProductScrapeUnavailableError,
)


def scrape_product(asin: str, geo_location: str):
    try:
        return scrape_product_details(asin, geo_location)
    except ValueError as exc:
        raise ProductScrapeConfigurationError() from exc
    except requests.Timeout as exc:
        raise ProductScrapeTimeoutError() from exc
    except requests.HTTPError as exc:
        upstream_status_code = None
        if exc.response is not None:
            upstream_status_code = exc.response.status_code

        raise ProductScrapeProviderError(
            details={"upstream_status_code": upstream_status_code},
        ) from exc
    except requests.RequestException as exc:
        raise ProductScrapeUnavailableError() from exc
