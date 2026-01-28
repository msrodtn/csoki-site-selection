#!/usr/bin/env python3
"""
Batch geocode CSV files using US Census Bureau Geocoder.

The Census Batch Geocoder is free, requires no API key, and can process
up to 10,000 addresses per request.

Usage:
    python scripts/batch_geocode.py --all
    python scripts/batch_geocode.py --file csoki_all_stores.csv
"""

import argparse
import csv
import logging
import sys
import time
from io import StringIO
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# US Census Bureau Batch Geocoder endpoint
CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"
VINTAGE = "Current_Current"

# Process in smaller batches for reliability
BATCH_SIZE = 500

# Data directory
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "competitors"

# CSV files to process
CSV_FILES = [
    "csoki_all_stores.csv",
    "russell_cellular_all_stores.csv",
    "tmobile_stores.csv",
    "uscellular_stores.csv",
    "verizon_corporate_stores.csv",
    "victra_stores.csv",
]


def read_csv_addresses(csv_path: Path) -> list[dict]:
    """Read addresses from CSV file."""
    addresses = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        # Check if first line is a header that doesn't match expected columns
        first_line = f.readline()
        f.seek(0)

        # Skip malformed header line (like "csoki_all_stores,,,")
        if not first_line.strip().startswith('street'):
            next(f)

        reader = csv.DictReader(f)

        for idx, row in enumerate(reader):
            street = row.get('street', '').strip()
            city = row.get('city', '').strip()
            state = row.get('state', '').strip().upper()
            postal_code = row.get('postal_code', '').strip()

            if city and state:
                addresses.append({
                    'id': str(idx),
                    'street': street,
                    'city': city,
                    'state': state,
                    'postal_code': postal_code,
                })

    return addresses


def geocode_batch(addresses: list[dict]) -> dict[str, tuple]:
    """
    Send batch to Census Geocoder, return dict of id -> (lat, lng).

    Census Geocoder input format: ID,Street,City,State,ZIP
    Census Geocoder output format: ID,Input Address,Match,Match Type,Output Address,Coordinates,TIGER Line ID,Side
    """
    if not addresses:
        return {}

    # Build CSV content for Census API
    csv_content = StringIO()
    writer = csv.writer(csv_content)

    for addr in addresses:
        writer.writerow([
            addr['id'],
            addr['street'],
            addr['city'],
            addr['state'],
            addr['postal_code']
        ])

    # Send request to Census Geocoder
    files = {
        'addressFile': ('addresses.csv', csv_content.getvalue(), 'text/csv')
    }
    data = {
        'benchmark': BENCHMARK,
        'vintage': VINTAGE,
    }

    try:
        response = requests.post(
            CENSUS_GEOCODER_URL,
            files=files,
            data=data,
            timeout=300  # 5 minute timeout for large batches
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Census API request failed: {e}")
        return {}

    # Parse response
    results = {}

    for line in response.text.strip().split('\n'):
        if not line:
            continue

        # Parse CSV line (handle quoted fields)
        try:
            reader = csv.reader(StringIO(line))
            parts = next(reader)
        except Exception:
            continue

        if len(parts) < 6:
            continue

        addr_id = parts[0]
        match_status = parts[2]

        # Only process matched addresses
        if match_status.lower() == 'match':
            try:
                # Coordinates are in format: "lng,lat" in field 5
                coords_str = parts[5]
                if ',' in coords_str:
                    lng, lat = coords_str.split(',')
                    results[addr_id] = (float(lat), float(lng))
            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse coordinates for {addr_id}: {e}")

    return results


def process_csv_file(csv_path: Path, output_path: Path) -> dict:
    """
    Read CSV, geocode addresses in batches, write enhanced CSV with coordinates.

    Returns stats dict with counts.
    """
    stats = {'total': 0, 'matched': 0, 'unmatched': 0}

    logger.info(f"Reading {csv_path.name}...")
    addresses = read_csv_addresses(csv_path)
    stats['total'] = len(addresses)
    logger.info(f"Found {len(addresses)} addresses to geocode")

    # Geocode in batches
    all_results = {}
    num_batches = (len(addresses) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(addresses), BATCH_SIZE):
        batch = addresses[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        logger.info(f"Processing batch {batch_num}/{num_batches} ({len(batch)} addresses)...")

        results = geocode_batch(batch)
        all_results.update(results)

        logger.info(f"Batch {batch_num}: {len(results)} matches")

        # Small delay between batches to be nice to the API
        if i + BATCH_SIZE < len(addresses):
            time.sleep(1)

    stats['matched'] = len(all_results)
    stats['unmatched'] = stats['total'] - stats['matched']

    # Write enhanced CSV
    logger.info(f"Writing output to {output_path.name}...")

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['street', 'city', 'state', 'postal_code', 'latitude', 'longitude'])

        for addr in addresses:
            coords = all_results.get(addr['id'])
            lat = coords[0] if coords else ''
            lng = coords[1] if coords else ''

            writer.writerow([
                addr['street'],
                addr['city'],
                addr['state'],
                addr['postal_code'],
                lat,
                lng
            ])

    logger.info(f"Complete: {stats['matched']}/{stats['total']} addresses geocoded ({stats['unmatched']} unmatched)")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Batch geocode competitor store CSV files using US Census Geocoder'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all CSV files'
    )
    parser.add_argument(
        '--file',
        type=str,
        help='Process a specific CSV file'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory (default: overwrite input files)'
    )

    args = parser.parse_args()

    if not args.all and not args.file:
        parser.print_help()
        sys.exit(1)

    # Determine output directory
    output_dir = Path(args.output_dir) if args.output_dir else DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine files to process
    files_to_process = CSV_FILES if args.all else [args.file]

    all_stats = {}

    for filename in files_to_process:
        csv_path = DATA_DIR / filename

        if not csv_path.exists():
            logger.warning(f"File not found: {csv_path}")
            continue

        output_path = output_dir / filename

        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {filename}")
        logger.info(f"{'='*60}")

        stats = process_csv_file(csv_path, output_path)
        all_stats[filename] = stats

    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")

    total_addresses = 0
    total_matched = 0

    for filename, stats in all_stats.items():
        total_addresses += stats['total']
        total_matched += stats['matched']
        match_pct = (stats['matched'] / stats['total'] * 100) if stats['total'] > 0 else 0
        logger.info(f"{filename}: {stats['matched']}/{stats['total']} ({match_pct:.1f}%)")

    overall_pct = (total_matched / total_addresses * 100) if total_addresses > 0 else 0
    logger.info(f"\nTotal: {total_matched}/{total_addresses} ({overall_pct:.1f}%)")


if __name__ == '__main__':
    main()
