"""
Ingestion job: scrape product + competitors from Oxylabs and write JSON
snapshots to a storage path that Databricks bronze notebooks will pick up.

Usage:
    # Single ASIN:
    uv run python ingestion/jobs/ingest_products.py \
        --asin B0FY52GZFG \
        --domain com \
        --geo 10001 \
        --output ./data

    # Batch from manifest (one ASIN per line):
    uv run python ingestion/jobs/ingest_products.py \
        --manifest ingestion/asins.txt \
        --output s3://bucket/pricesense

Output layout (mirrors what 01_bronze_ingestion.py expects):
    {output}/products/{YYYY-MM-DD}/{asin}.json
    {output}/competitors/{YYYY-MM-DD}/{asin}_competitors.json
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

from ingestion.oxylabs_client.client import scrape_competitors, scrape_product_details

logger = logging.getLogger(__name__)


def _load_asins(manifest_path: str) -> list[str]:
    lines = Path(manifest_path).read_text(encoding="utf-8").splitlines()
    return [line.strip().upper() for line in lines if line.strip() and not line.startswith("#")]


def _write_json(base: str, sub: str, data: dict | list) -> None:
    path = f"{base.rstrip('/')}/{sub}"
    with fsspec.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
    logger.debug("Written: %s", path)


def ingest_product(asin: str, domain: str, geo: str, output_root: str, date_str: str) -> None:
    product = scrape_product_details(asin, geo_location=geo, domain=domain)
    product["scraped_at"] = datetime.now(timezone.utc).isoformat()

    sub = f"products/{date_str}/{asin}.json"
    _write_json(output_root, sub, product)
    logger.info("Product saved asin=%s price=%s stock=%s", asin, product.get("price"), product.get("stock"))


def ingest_competitors(asin: str, domain: str, geo: str, output_root: str, date_str: str) -> None:
    competitors = scrape_competitors(asin, domain=domain, geo_location=geo)

    fetch_time = datetime.now(timezone.utc).isoformat()
    for comp in competitors:
        comp["parent_asin"] = asin
        comp["fetched_at"] = fetch_time

    sub = f"competitors/{date_str}/{asin}_competitors.json"
    _write_json(output_root, sub, competitors)
    logger.info("Competitors saved asin=%s count=%d", asin, len(competitors))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape product + competitors and write to storage")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--asin",     help="Single Amazon ASIN to scrape")
    group.add_argument("--manifest", help="Path to file with one ASIN per line")

    parser.add_argument("--domain",           default="com",   help="Amazon domain (default: com)")
    parser.add_argument("--geo",              default="10001", help="Zip/postal code for geo-pricing")
    parser.add_argument("--output",           default="./data",help="Output root path (local or s3://, abfss://, gs://)")
    parser.add_argument("--date",             default="",      help="Scrape date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--skip-competitors", action="store_true", help="Skip competitor scrape")
    parser.add_argument("--log-level",        default="INFO",  help="Logging level (default: INFO)")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    date_str = args.date.strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    asins = [args.asin.strip().upper()] if args.asin else _load_asins(args.manifest)

    logger.info(
        "PriceSenseAi bronze ingestion started asins=%d domain=amazon.%s geo=%s date=%s output=%s",
        len(asins), args.domain, args.geo, date_str, args.output,
    )

    ok = failed = 0
    for asin in asins:
        try:
            ingest_product(asin, args.domain, args.geo, args.output, date_str)
            if not args.skip_competitors:
                ingest_competitors(asin, args.domain, args.geo, args.output, date_str)
            ok += 1
        except Exception as exc:
            logger.error("Ingestion failed asin=%s error=%s", asin, exc, exc_info=True)
            failed += 1

    logger.info("Bronze ingestion complete ok=%d failed=%d. Files ready for 01_bronze_ingestion.py", ok, failed)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
