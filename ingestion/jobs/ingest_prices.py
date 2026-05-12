"""
Lightweight price-only snapshot job.

Use this when you want daily price history without the overhead of a full product
scrape. Reads tracked ASINs from a manifest file (or accepts them as CLI args),
fetches current price + stock via Oxylabs, and writes one JSON file per ASIN into
the products/ snapshot path — the same path that 01_bronze_ingestion.py reads.

Usage:
    # Scrape a single ASIN:
    uv run python ingestion/jobs/ingest_prices.py \
        --asin B0FY52GZFG \
        --output ./data

    # Scrape all ASINs listed in a manifest file (one ASIN per line):
    uv run python ingestion/jobs/ingest_prices.py \
        --manifest ./asins.txt \
        --output ./data

    # Full options:
    uv run python ingestion/jobs/ingest_prices.py \
        --manifest ./asins.txt \
        --domain com \
        --geo 10001 \
        --output ./data \
        --date 2026-05-10

Output layout (same as ingest_products.py so bronze ingestion picks it up):
    {output}/products/{YYYY-MM-DD}/{asin}.json
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

import fsspec

from ingestion.oxylabs_client.client import scrape_product_details

logger = logging.getLogger(__name__)


def _write_json(base: str, sub: str, data: dict | list) -> None:
    path = f"{base.rstrip('/')}/{sub}"
    with fsspec.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def _load_asins(manifest_path: str) -> list[str]:
    lines = Path(manifest_path).read_text(encoding="utf-8").splitlines()
    return [line.strip().upper() for line in lines if line.strip() and not line.startswith("#")]


def snapshot_price(asin: str, domain: str, geo: str, output_root: str, date_str: str) -> None:
    product = scrape_product_details(asin, geo_location=geo, domain=domain)
    product["scraped_at"] = datetime.now(timezone.utc).isoformat()

    sub = f"products/{date_str}/{asin}.json"
    _write_json(output_root, sub, product)
    logger.info("Snapshot written asin=%s price=%s stock=%s", asin, product.get("price"), product.get("stock"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight daily price snapshot job")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--asin",     help="Single ASIN to snapshot")
    group.add_argument("--manifest", help="Path to a file with one ASIN per line")

    parser.add_argument("--domain",    default="com",   help="Amazon domain (default: com)")
    parser.add_argument("--geo",       default="10001", help="Zip/postal code for geo-pricing")
    parser.add_argument("--output",    default="./data", help="Output root path")
    parser.add_argument("--date",      default="",       help="Scrape date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--log-level", default="INFO",   help="Logging level (default: INFO)")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    date_str = args.date.strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    asins = [args.asin.strip().upper()] if args.asin else _load_asins(args.manifest)

    logger.info(
        "PriceSenseAi price snapshot job started asins=%d domain=amazon.%s geo=%s date=%s output=%s",
        len(asins), args.domain, args.geo, date_str, args.output,
    )

    ok = failed = 0
    for asin in asins:
        try:
            snapshot_price(asin, args.domain, args.geo, args.output, date_str)
            ok += 1
        except Exception as exc:
            logger.error("Snapshot failed asin=%s error=%s", asin, exc, exc_info=True)
            failed += 1

    logger.info("Price snapshot job complete ok=%d failed=%d", ok, failed)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
