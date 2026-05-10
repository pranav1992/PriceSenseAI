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
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from ingestion.oxylabs_client.client import scrape_product_details


def _resolve_output(base: str, sub: str) -> Path:
    if base.startswith(("s3://", "abfss://", "gs://")):
        raise NotImplementedError(
            f"Cloud path '{base}' detected. "
            "Replace _resolve_output() with a cloud write helper (boto3, azure-storage-blob, etc.)."
        )
    path = Path(base) / sub
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, data: dict | list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def _load_asins(manifest_path: str) -> list[str]:
    lines = Path(manifest_path).read_text(encoding="utf-8").splitlines()
    return [line.strip().upper() for line in lines if line.strip() and not line.startswith("#")]


def snapshot_price(asin: str, domain: str, geo: str, output_root: str, date_str: str) -> None:
    product = scrape_product_details(asin, geo_location=geo, domain=domain)
    product["scraped_at"] = datetime.now(timezone.utc).isoformat()

    out_path = _resolve_output(output_root, f"products/{date_str}/{asin}.json")
    _write_json(out_path, product)
    print(f"  [{asin}] price={product.get('price')}  stock={product.get('stock')}  → {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight daily price snapshot job")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--asin",     help="Single ASIN to snapshot")
    group.add_argument("--manifest", help="Path to a file with one ASIN per line")

    parser.add_argument("--domain",  default="com",   help="Amazon domain (default: com)")
    parser.add_argument("--geo",     default="10001", help="Zip/postal code for geo-pricing")
    parser.add_argument("--output",  default="./data", help="Output root path")
    parser.add_argument("--date",    default="",       help="Scrape date YYYY-MM-DD (default: today UTC)")
    args = parser.parse_args()

    date_str = args.date.strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    asins = [args.asin.strip().upper()] if args.asin else _load_asins(args.manifest)

    print("PriceSenseAi — Daily Price Snapshot Job")
    print(f"  ASINs  : {len(asins)}")
    print(f"  Domain : amazon.{args.domain}")
    print(f"  Geo    : {args.geo}")
    print(f"  Date   : {date_str}")
    print(f"  Output : {args.output}")
    print()

    ok = failed = 0
    for asin in asins:
        try:
            snapshot_price(asin, args.domain, args.geo, args.output, date_str)
            ok += 1
        except Exception as exc:
            print(f"  [{asin}] ERROR: {exc}")
            failed += 1

    print(f"\n✓ Done — {ok} snapshots written, {failed} failed.")
    print("Files are ready for 01_bronze_ingestion.py to pick up.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
