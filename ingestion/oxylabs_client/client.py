import os

import requests
from dotenv import load_dotenv

load_dotenv()

OXYLABS_API_URL = os.getenv("OXYLABS_API_URL")
REQUEST_TIMEOUT_SECONDS = 60


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
    if not OXYLABS_API_URL:
        raise ValueError("OXYLABS_API_URL must be set in the environment")

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


def scrape_product_details(asin, geo_location):
    payload = {
        "source": "amazon_product",
        "query": asin,
        "geo_location": geo_location,
        # "domain": domain,
        "parse": True,
    }
    response = post_query(payload)
    response.raise_for_status()

    content = extract_content(response.json())
    normalized = normalize_product(content)
    if not normalized.get("asin"):
        normalized["asin"] = asin

    # normalized["amazon_domain"] = domain
    normalized["geo_location"] = geo_location
    return normalized


def normalize_competitor(item: dict) -> dict:
    # amazon_search prices are plain numbers; amazon_product returns dicts
    price_data = item.get("price")
    price = price_data.get("value") if isinstance(price_data, dict) else price_data

    images = item.get("images") or []
    if isinstance(images, str):
        images = [images]

    return {
        "asin": item.get("asin"),
        "title": item.get("title"),
        "url": item.get("url"),
        "brand": item.get("brand"),
        "price": price,
        "currency": item.get("currency"),
        "rating": item.get("rating"),
        "images": [img for img in images if isinstance(img, str)],
    }


def scrape_competitors(asin: str, domain: str, geo_location: str) -> list:
    payload = {
        "source": "amazon_search",
        "domain": domain,
        "query": asin,
        "pages": 1,
        "parse": True,
        "context": [
            {"key": "currency", "value": "USD"},
            {"key": "sort_by", "value": "featured"},
        ],
    }
    if geo_location:
        payload["geo_location"] = geo_location

    response = post_query(payload)
    response.raise_for_status()

    content = extract_content(response.json())
    organic = []
    if isinstance(content, dict):
        results = content.get("results") or {}
        organic = results.get("organic") if isinstance(results, dict) else []

    return [normalize_competitor(item) for item in (organic or []) if item.get("asin")]


if __name__ == "__main__":
    print(scrape_product_details("B07FZ8S74R", "90210"))
