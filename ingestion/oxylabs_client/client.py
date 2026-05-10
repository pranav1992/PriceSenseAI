import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OXYLABS_API_URL = os.getenv("OXYLABS_API_URL", "https://realtime.oxylabs.io/v1/queries")
REQUEST_TIMEOUT_SECONDS = 120
SEARCH_STRATEGIES = ["featured", "price_low_to_high", "price_high_to_low", "average_review"]


def extract_content(payload):
    if isinstance(payload, dict):
        if "results" in payload and isinstance(payload["results"], list) and payload["results"]:
            first = payload["results"][0]
            if isinstance(first, dict) and "content" in first:
                return first["content"] or {}
        if "content" in payload:
            return payload.get("content", {})
    return payload


def post_query(payload):
    username = os.getenv("OXYLABS_USERNAME")
    password = os.getenv("OXYLABS_PASSWORD")

    if not username or not password:
        raise ValueError("OXYLABS_USERNAME and OXYLABS_PASSWORD must be set in the environment")

    return requests.post(
        OXYLABS_API_URL,
        json=payload,
        auth=(username, password),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def normalize_product(content):
    if not isinstance(content, dict):
        content = {}

    category_path = []
    if content.get("category_path"):
        category_path = [cat.strip() for cat in content["category_path"] if cat]

    return {
        "asin": content.get("asin"),
        "url": content.get("url"),
        "brand": content.get("brand"),
        "price": content.get("price"),
        "stock": content.get("stock"),
        "title": content.get("title"),
        "rating": content.get("rating"),
        "images": content.get("images", []),
        "categories": content.get("category", []) or content.get("categories", []),
        "category_path": category_path,
        "currency": content.get("currency"),
        "buybox": content.get("buybox", []),
        "product_overview": content.get("product_overview", []),
    }


def scrape_product_details(asin, geo_location, domain="com"):
    logger.info("Scraping product asin=%s domain=%s geo=%s", asin, domain, geo_location)
    payload = {
        "source": "amazon_product",
        "query": asin,
        "domain": domain,
        "geo_location": geo_location,
        "parse": True,
    }
    response = post_query(payload)
    response.raise_for_status()

    content = extract_content(response.json())
    normalized = normalize_product(content)
    if not normalized.get("asin"):
        normalized["asin"] = asin

    normalized["amazon_domain"] = domain
    normalized["geo_location"] = geo_location
    logger.info("Product scraped asin=%s price=%s stock=%s", asin, normalized.get("price"), normalized.get("stock"))
    return normalized


def clean_product_name(title: str) -> str:
    """Strip marketing suffixes after '-' or '|' for a cleaner search query."""
    if "-" in title:
        title = title.split("-")[0]
    if "|" in title:
        title = title.split("|")[0]
    return title.strip()


def extract_search_results(content: dict) -> list:
    items = []
    if not isinstance(content, dict):
        return items

    if "results" in content:
        results = content["results"]
        if isinstance(results, dict):
            items.extend(results.get("organic") or [])
            items.extend(results.get("paid") or [])
    elif isinstance(content.get("products"), list):
        items.extend(content["products"])

    return items


def normalize_search_result(item: dict, domain: str) -> dict | None:
    asin = item.get("asin") or item.get("product_asin")
    title = item.get("title")
    if not asin:
        return None
    return {
        "asin": asin,
        "title": title,
        "price": item.get("price"),
        "currency": item.get("currency"),
        "rating": item.get("rating"),
        "images": item.get("images") or [],
        "brand": item.get("brand"),
        "url": f"https://www.amazon.{domain}/dp/{asin}",
        "amazon_domain": domain,
    }


def search_competitors(query_title: str, domain: str, geo_location: str = "") -> list:
    """
    Single featured search for competitors by cleaned product title.
    Returns a deduplicated list of competitor dicts with constructed URLs.
    """
    search_query = clean_product_name(query_title)
    logger.info("Searching competitors for query=%r domain=%s", search_query, domain)

    payload = {
        "source": "amazon_search",
        "query": search_query,
        "domain": domain,
        "start_page": 1,
        "pages": 1,
        "parse": True,
        "sort_by": SEARCH_STRATEGIES[0],
    }
    if geo_location:
        payload["geo_location"] = geo_location

    content = extract_content(post_query(payload).json())

    results = []
    seen_asins: set[str] = set()
    for item in extract_search_results(content):
        result = normalize_search_result(item, domain)
        if result and result["asin"] not in seen_asins:
            seen_asins.add(result["asin"])
            results.append(result)

    logger.info("Found %d competitors", len(results))
    return results


def scrape_competitors(asin: str, domain: str, geo_location: str) -> list:
    """
    Competitor pipeline (2 API calls total):
      1. Scrape the source product to get its title.
      2. Search Amazon by cleaned title and return results directly.
    """
    logger.info("Starting competitor scrape for asin=%s", asin)
    source = scrape_product_details(asin, geo_location, domain)
    title = source.get("title") or asin

    results = [
        c for c in search_competitors(title, domain, geo_location)
        if c.get("asin") != asin
    ]
    logger.info("Competitor scrape complete asin=%s count=%d", asin, len(results))
    return results


if __name__ == "__main__":
    import pprint
    pprint.pprint(scrape_product_details("B07FZ8S74R", "90210"))
