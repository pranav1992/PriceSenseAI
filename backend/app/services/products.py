import requests
from sqlalchemy.orm import Session

from ingestion.oxylabs_client.client import scrape_product_details

from ..models.product import Product
from .product_exceptions import (
    ProductScrapeConfigurationError,
    ProductScrapeProviderError,
    ProductScrapeTimeoutError,
    ProductScrapeUnavailableError,
)


def scrape_product(asin: str, geo_location: str, domain: str = "com", db: Session | None = None):
    try:
        data = scrape_product_details(asin, geo_location, domain)
    except ValueError as exc:
        raise ProductScrapeConfigurationError() from exc
    except requests.Timeout as exc:
        raise ProductScrapeTimeoutError() from exc
    except requests.HTTPError as exc:
        upstream_status_code = exc.response.status_code if exc.response is not None else None
        raise ProductScrapeProviderError(details={"upstream_status_code": upstream_status_code}) from exc
    except requests.RequestException as exc:
        raise ProductScrapeUnavailableError() from exc

    if db is not None:
        _upsert_product(db, data)

    return data


def _upsert_product(db: Session, data: dict) -> None:
    asin = data.get("asin")
    if not asin:
        return

    product = db.get(Product, asin)
    if product is None:
        product = Product(asin=asin)
        db.add(product)

    product.title = data.get("title")
    product.url = data.get("url")
    product.brand = data.get("brand")
    product.price = data.get("price")
    product.currency = data.get("currency")
    product.stock = data.get("stock")
    product.rating = data.get("rating")
    product.images = data.get("images", [])
    product.categories = data.get("categories", [])
    product.category_path = data.get("category_path", [])
    product.buybox = data.get("buybox", [])
    product.product_overview = data.get("product_overview", [])
    product.amazon_domain = data.get("amazon_domain")
    product.geo_location = data.get("geo_location")

    db.commit()
