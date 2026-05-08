import requests
from sqlalchemy.orm import Session

from ingestion.oxylabs_client.client import scrape_competitors

from ..models.competitor import Competitor
from .product_exceptions import (
    ProductScrapeConfigurationError,
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
    ProductScrapeUnavailableError,
)


def get_competitors(parent_asin: str, db: Session) -> list:
    rows = db.query(Competitor).filter(Competitor.parent_asin == parent_asin).all()
    return [r.to_dict() for r in rows]


def fetch_competitors(asin: str, domain: str, geo_location: str, db: Session) -> list:
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

    _save_competitors(db, asin, results)
    return results


def _save_competitors(db: Session, parent_asin: str, results: list) -> None:
    db.query(Competitor).filter(Competitor.parent_asin == parent_asin).delete()
    for item in results:
        if not item.get("asin"):
            continue
        db.add(Competitor(
            parent_asin=parent_asin,
            asin=item["asin"],
            title=item.get("title"),
            url=item.get("url"),
            brand=item.get("brand"),
            price=item.get("price"),
            currency=item.get("currency"),
            rating=item.get("rating"),
            images=item.get("images", []),
            amazon_domain=item.get("amazon_domain"),
        ))
    db.commit()
