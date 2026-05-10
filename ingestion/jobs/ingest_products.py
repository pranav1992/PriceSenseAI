"""
Ingestion job: scrape product + competitors from Oxylabs and write JSON
snapshots to a storage path that Databricks bronze notebooks will pick up.

Usage:
    uv run python ingestion/jobs/ingest_products.py \
        --asin B0FY52GZFG \
        --domain com \
        --geo 10001 \
        --output ./data                 # local path, or s3://bucket/pricesense, etc.

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

from ingestion.oxylabs_client.client import scrape_competitors, scrape_product_details

logger = logging.getLogger(__name__)


def _resolve_output(base: str, sub: str) -> Path:
    """Return a local Path for the output file. Cloud paths (s3://, abfss://) are
    not writable with plain pathlib — for cloud, swap this for boto3 / azure-storage."""
    if base.startswith(("s3://", "abfss://", "gs://")):
        raise NotImplementedError(
            f"Cloud path '{base}' detected. "
            "Install the relevant SDK (boto3, azure-storage-blob, google-cloud-storage) "
            "and replace _resolve_output() with a cloud write function."
        )
    path = Path(base) / sub
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, data: dict | list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
    logger.debug("Written: %s", path)


def ingest_product(asin: str, domain: str, geo: str, output_root: str, date_str: str) -> None:
    product = scrape_product_details(asin, geo_location=geo, domain=domain)
    product["scraped_at"] = datetime.now(timezone.utc).isoformat()

    out_path = _resolve_output(output_root, f"products/{date_str}/{asin}.json")
    _write_json(out_path, product)
    logger.info("Product saved asin=%s price=%s stock=%s path=%s", asin, product.get("price"), product.get("stock"), out_path)


def ingest_competitors(asin: str, domain: str, geo: str, output_root: str, date_str: str) -> None:
    competitors = scrape_competitors(asin, domain=domain, geo_location=geo)

    fetch_time = datetime.now(timezone.utc).isoformat()
    for comp in competitors:
        comp["parent_asin"] = asin
        comp["fetched_at"] = fetch_time

    out_path = _resolve_output(output_root, f"competitors/{date_str}/{asin}_competitors.json")
    _write_json(out_path, competitors)
    logger.info("Competitors saved asin=%s count=%d path=%s", asin, len(competitors), out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape product + competitors and write to storage")
    parser.add_argument("--asin",             required=True,   help="Amazon ASIN to scrape")
    parser.add_argument("--domain",           default="com",   help="Amazon domain (default: com)")
    parser.add_argument("--geo",              default="10001", help="Zip/postal code for geo-pricing")
    parser.add_argument("--output",           default="./data",help="Output root path (local or cloud)")
    parser.add_argument("--date",             default="",      help="Scrape date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--skip-competitors", action="store_true", help="Skip competitor scrape")
    parser.add_argument("--log-level",        default="INFO",  help="Logging level (default: INFO)")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    asin     = args.asin.strip().upper()
    date_str = args.date.strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(
        "PriceSenseAi bronze ingestion job started asin=%s domain=amazon.%s geo=%s date=%s output=%s",
        asin, args.domain, args.geo, date_str, args.output,
    )

    ingest_product(asin, args.domain, args.geo, args.output, date_str)
    if not args.skip_competitors:
        ingest_competitors(asin, args.domain, args.geo, args.output, date_str)

    logger.info("Bronze ingestion complete. Files ready for 01_bronze_ingestion.py")


if __name__ == "__main__":
    main()
