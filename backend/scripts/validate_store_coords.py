#!/usr/bin/env python3
"""
Validate store coordinates to identify problematic geocoding data.

This script identifies stores with:
- Null or zero coordinates
- Coordinates outside continental US bounds
- Significant coordinate mismatches when re-geocoded
- Coordinates that may cause Mapbox Matrix API failures

Usage:
    python scripts/validate_store_coords.py                    # Audit only
    python scripts/validate_store_coords.py --fix              # Fix issues
    python scripts/validate_store_coords.py --brand csoki      # Check specific brand
    python scripts/validate_store_coords.py --limit 100        # Limit to N stores

Requires GOOGLE_PLACES_API_KEY environment variable for re-geocoding.
"""

import os
import sys
import time
import argparse
import json
import math
from datetime import datetime
from typing import Optional
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


# Continental US bounding box (approximate)
US_BOUNDS = {
    "min_lat": 24.0,   # Southern tip of Florida
    "max_lat": 49.5,   # Northern border
    "min_lng": -125.0, # West coast
    "max_lng": -66.0,  # East coast
}

# How far coordinates can be from geocoded result before flagging (in miles)
MISMATCH_THRESHOLD_MILES = 0.5


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles using Haversine formula."""
    R = 3959  # Earth radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def geocode_address(address: str, api_key: str) -> Optional[tuple[float, float]]:
    """
    Geocode an address using Google Geocoding API.
    Returns (latitude, longitude) or None if failed.
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "OK" and data["results"]:
            location = data["results"][0]["geometry"]["location"]
            return (location["lat"], location["lng"])
        return None
    except Exception:
        return None


def validate_coordinates(lat: Optional[float], lng: Optional[float]) -> list[str]:
    """Validate coordinates and return list of issues."""
    issues = []

    if lat is None or lng is None:
        issues.append("NULL_COORDS")
        return issues

    if lat == 0 and lng == 0:
        issues.append("ZERO_COORDS")
        return issues

    if lat == 0 or lng == 0:
        issues.append("ZERO_VALUE")

    if not (US_BOUNDS["min_lat"] <= lat <= US_BOUNDS["max_lat"]):
        issues.append("LAT_OUT_OF_BOUNDS")

    if not (US_BOUNDS["min_lng"] <= lng <= US_BOUNDS["max_lng"]):
        issues.append("LNG_OUT_OF_BOUNDS")

    return issues


def build_address(street: str, city: str, state: str, postal_code: str) -> str:
    """Build a full address string from components."""
    parts = []
    if street:
        parts.append(street)
    if city:
        parts.append(city)
    if state:
        parts.append(state)
    if postal_code:
        parts.append(postal_code)
    parts.append("USA")
    return ", ".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Validate store coordinates")
    parser.add_argument("--fix", action="store_true", help="Fix invalid coordinates")
    parser.add_argument("--brand", type=str, help="Only check specific brand")
    parser.add_argument("--limit", type=int, help="Limit number of stores to check")
    parser.add_argument("--geocode", action="store_true", help="Re-geocode and compare (slower)")
    parser.add_argument("--output", type=str, help="Output JSON report file")
    args = parser.parse_args()

    # Check for API key if geocoding
    api_key = settings.GOOGLE_PLACES_API_KEY
    if args.geocode and not api_key:
        print("ERROR: GOOGLE_PLACES_API_KEY required for --geocode option")
        sys.exit(1)

    # Connect to database
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Build query
    query = """
        SELECT id, brand, street, city, state, postal_code, latitude, longitude
        FROM stores
    """
    params = {}

    conditions = []
    if args.brand:
        conditions.append("brand = :brand")
        params["brand"] = args.brand.lower()

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id"

    if args.limit:
        query += " LIMIT :limit"
        params["limit"] = args.limit

    print(f"\n{'='*70}")
    print(f"STORE COORDINATE VALIDATION")
    print(f"{'='*70}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.brand:
        print(f"Brand filter: {args.brand}")
    if args.limit:
        print(f"Limit: {args.limit}")
    print(f"Geocode check: {args.geocode}")
    print(f"Fix mode: {args.fix}")
    print(f"{'='*70}\n")

    try:
        result = session.execute(text(query), params)
        stores = result.fetchall()

        total = len(stores)
        print(f"Found {total} stores to validate\n")

        # Tracking
        issues_found = {
            "null_coords": [],
            "zero_coords": [],
            "out_of_bounds": [],
            "geocode_mismatch": [],
            "geocode_failed": [],
            "no_address": [],
        }
        fixed = 0
        checked = 0

        for i, store in enumerate(stores):
            store_id, brand, street, city, state, postal_code, lat, lng = store
            checked += 1

            # Progress
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i+1}/{total} stores...")

            # Basic validation
            coord_issues = validate_coordinates(lat, lng)

            if "NULL_COORDS" in coord_issues:
                issues_found["null_coords"].append({
                    "id": store_id,
                    "brand": brand,
                    "address": build_address(street, city, state, postal_code),
                })
                continue

            if "ZERO_COORDS" in coord_issues:
                issues_found["zero_coords"].append({
                    "id": store_id,
                    "brand": brand,
                    "address": build_address(street, city, state, postal_code),
                })
                continue

            if "LAT_OUT_OF_BOUNDS" in coord_issues or "LNG_OUT_OF_BOUNDS" in coord_issues:
                issues_found["out_of_bounds"].append({
                    "id": store_id,
                    "brand": brand,
                    "lat": lat,
                    "lng": lng,
                    "issues": coord_issues,
                })

            # Geocode check (optional, slower)
            if args.geocode:
                address = build_address(street, city, state, postal_code)

                if not street and not city:
                    issues_found["no_address"].append({
                        "id": store_id,
                        "brand": brand,
                    })
                    continue

                new_coords = geocode_address(address, api_key)

                if new_coords:
                    new_lat, new_lng = new_coords
                    distance = haversine_distance(lat, lng, new_lat, new_lng)

                    if distance > MISMATCH_THRESHOLD_MILES:
                        issues_found["geocode_mismatch"].append({
                            "id": store_id,
                            "brand": brand,
                            "address": address,
                            "old_lat": lat,
                            "old_lng": lng,
                            "new_lat": new_lat,
                            "new_lng": new_lng,
                            "distance_miles": round(distance, 2),
                        })

                        # Fix if requested
                        if args.fix:
                            session.execute(text("""
                                UPDATE stores
                                SET latitude = :lat, longitude = :lng
                                WHERE id = :id
                            """), {"lat": new_lat, "lng": new_lng, "id": store_id})
                            fixed += 1
                else:
                    issues_found["geocode_failed"].append({
                        "id": store_id,
                        "brand": brand,
                        "address": address,
                    })

                # Rate limiting
                time.sleep(0.1)

        # Commit fixes
        if args.fix and fixed > 0:
            session.commit()
            print(f"\n✓ Fixed {fixed} stores")

        # Print summary
        print(f"\n{'='*70}")
        print("VALIDATION SUMMARY")
        print(f"{'='*70}")
        print(f"Total stores checked: {checked}")
        print(f"")
        print(f"Issues found:")
        print(f"  - Null coordinates:     {len(issues_found['null_coords'])}")
        print(f"  - Zero coordinates:     {len(issues_found['zero_coords'])}")
        print(f"  - Out of US bounds:     {len(issues_found['out_of_bounds'])}")
        if args.geocode:
            print(f"  - Geocode mismatch:     {len(issues_found['geocode_mismatch'])}")
            print(f"  - Geocode failed:       {len(issues_found['geocode_failed'])}")
            print(f"  - No address:           {len(issues_found['no_address'])}")
        if args.fix:
            print(f"\nCoordinates fixed: {fixed}")
        print(f"{'='*70}\n")

        # Print details
        if issues_found["null_coords"]:
            print("\n📍 Stores with NULL coordinates:")
            for item in issues_found["null_coords"][:10]:
                print(f"   ID {item['id']} ({item['brand']}): {item['address']}")
            if len(issues_found["null_coords"]) > 10:
                print(f"   ... and {len(issues_found['null_coords']) - 10} more")

        if issues_found["zero_coords"]:
            print("\n📍 Stores with ZERO coordinates:")
            for item in issues_found["zero_coords"][:10]:
                print(f"   ID {item['id']} ({item['brand']}): {item['address']}")
            if len(issues_found["zero_coords"]) > 10:
                print(f"   ... and {len(issues_found['zero_coords']) - 10} more")

        if issues_found["out_of_bounds"]:
            print("\n📍 Stores with OUT OF BOUNDS coordinates:")
            for item in issues_found["out_of_bounds"][:10]:
                print(f"   ID {item['id']} ({item['brand']}): ({item['lat']}, {item['lng']})")
            if len(issues_found["out_of_bounds"]) > 10:
                print(f"   ... and {len(issues_found['out_of_bounds']) - 10} more")

        if issues_found["geocode_mismatch"]:
            print("\n📍 Stores with GEOCODE MISMATCH (>{} miles):".format(MISMATCH_THRESHOLD_MILES))
            for item in issues_found["geocode_mismatch"][:10]:
                print(f"   ID {item['id']} ({item['brand']}): moved {item['distance_miles']} mi")
                print(f"      Address: {item['address']}")
                print(f"      Old: ({item['old_lat']}, {item['old_lng']})")
                print(f"      New: ({item['new_lat']}, {item['new_lng']})")
            if len(issues_found["geocode_mismatch"]) > 10:
                print(f"   ... and {len(issues_found['geocode_mismatch']) - 10} more")

        # Output JSON report
        if args.output:
            report = {
                "timestamp": datetime.now().isoformat(),
                "total_checked": checked,
                "issues": {
                    "null_coords": len(issues_found["null_coords"]),
                    "zero_coords": len(issues_found["zero_coords"]),
                    "out_of_bounds": len(issues_found["out_of_bounds"]),
                    "geocode_mismatch": len(issues_found["geocode_mismatch"]),
                    "geocode_failed": len(issues_found["geocode_failed"]),
                },
                "details": issues_found,
                "fixed": fixed,
            }
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report saved to: {args.output}")

        # Return exit code based on issues
        total_issues = sum(len(v) for v in issues_found.values())
        if total_issues > 0:
            print(f"\n⚠️  Found {total_issues} total issues")
            return 1
        else:
            print("\n✅ All coordinates valid!")
            return 0

    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
