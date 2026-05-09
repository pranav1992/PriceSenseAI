import requests

from ingestion.oxylabs_client.client import scrape_competitors

from ..repositories.competitor import CompetitorRepository
from .product_exceptions import (
    ProductScrapeConfigurationError,
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
    ProductScrapeUnavailableError,
)


def get_competitors(parent_asin: str, repo: CompetitorRepository) -> list:
    rows = repo.get_by_parent_asin(parent_asin)
    return [r.to_dict() for r in rows]


def fetch_competitors(asin: str, domain: str, geo_location: str, repo: CompetitorRepository) -> list:
    cached = repo.get_by_parent_asin(asin)
    if cached:
        return [row.to_dict() for row in cached]

    try:
        results = scrape_competitors(asin, domain, geo_location)
    except ValueError as exc:
        raise ProductScrapeConfigurationError() from exc
    except requests.Timeout as exc:
        raise ProductScrapeTimeoutError() from exc
    except requests.HTTPError as exc:
        upstream_status_code = exc.response.status_code if exc.response is not None else None
        raise ProductScrapeProviderError(details={"upstream_status_code": upstream_status_code}) from exc
    except requests.RequestException as exc:
        raise ProductScrapeUnavailableError() from exc

    repo.replace_for_parent(asin, results)
    return results
