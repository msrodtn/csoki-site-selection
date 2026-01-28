#!/usr/bin/env python3
"""
Script to import competitor data into the database.

Usage:
    python scripts/import_data.py --all           # Import all CSV files
    python scripts/import_data.py --brand csoki   # Import specific brand
    python scripts/import_data.py --geocode       # Import and geocode (slow)
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.services.data_import import import_all_competitors, import_csv_to_db, BRAND_FILE_MAPPING


def main():
    parser = argparse.ArgumentParser(description="Import competitor store data")
    parser.add_argument("--all", action="store_true", help="Import all competitor files")
    parser.add_argument("--brand", type=str, help="Import specific brand")
    parser.add_argument("--geocode", action="store_true", help="Geocode addresses (slow)")
    parser.add_argument("--data-dir", type=str, default="data/competitors",
                       help="Path to data directory")

    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)

    db = SessionLocal()

    try:
        if args.all:
            print(f"Importing all competitors from {data_dir}...")
            stats = import_all_competitors(db, data_dir, geocode=args.geocode)

            print("\n=== Import Summary ===")
            for brand, s in stats.items():
                if "error" in s:
                    print(f"  {brand}: {s['error']}")
                else:
                    print(f"  {brand}: {s['imported']} imported, {s['skipped']} skipped, {s['errors']} errors")

        elif args.brand:
            # Find the matching file
            filename = None
            for fn, brand in BRAND_FILE_MAPPING.items():
                if brand == args.brand.lower():
                    filename = fn
                    break

            if not filename:
                print(f"Error: Unknown brand '{args.brand}'")
                print(f"Available brands: {', '.join(BRAND_FILE_MAPPING.values())}")
                sys.exit(1)

            csv_path = data_dir / filename
            if not csv_path.exists():
                print(f"Error: File not found: {csv_path}")
                sys.exit(1)

            print(f"Importing {args.brand} from {csv_path}...")
            stats = import_csv_to_db(db, csv_path, args.brand.lower(), geocode=args.geocode)
            print(f"Done: {stats}")

        else:
            parser.print_help()

    finally:
        db.close()


if __name__ == "__main__":
    main()
