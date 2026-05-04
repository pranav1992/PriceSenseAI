import os

import requests
from dotenv import load_dotenv

load_dotenv()

OXYLABS_API_URL = os.getenv("OXYLABS_API_URL", "https://api.oxylabs.io/v1/queries")
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


def scrape_product_details(asin, geo_location, domain):
    payload = {
        "source": "amazon_product",
        "query": asin,
        "geo_location": geo_location,
        "domain": domain,
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
    return normalized
