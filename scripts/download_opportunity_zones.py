#!/usr/bin/env python3
"""
Download Opportunity Zone (OZ 1.0) designated census tract boundaries from
the HUD ArcGIS Feature Service.

Usage:
    python scripts/download_opportunity_zones.py
    python scripts/download_opportunity_zones.py TN CA TX   # specific states only

Output:
    mapbox-tilesets/national_oz_tracts.ndjson

Data Source:
    HUD ArcGIS Feature Service - 8,764 designated OZ census tracts
    https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/Opportunity_Zones/FeatureServer/0
"""

import httpx
import asyncio
import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "mapbox-tilesets"

# HUD Opportunity Zones Feature Service
OZ_FEATURE_SERVICE = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/"
    "Opportunity_Zones/FeatureServer/13/query"
)

# State FIPS codes (all 50 + DC + territories)
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "PR": "72",
    "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48",
    "UT": "49", "VT": "50", "VA": "51", "VI": "78", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56", "AS": "60", "GU": "66",
    "MP": "69",
}

# Reverse lookup: FIPS -> state abbreviation
FIPS_TO_STATE = {v: k for k, v in STATE_FIPS.items()}

# Rate limiting
SLEEP_BETWEEN_CALLS = 0.5
MAX_RETRIES = 3
BATCH_SIZE = 1000  # HUD allows up to 2000, use 1000 for safety


async def fetch_with_retry(client: httpx.AsyncClient, url: str, params: dict,
                           description: str):
    """Fetch URL with exponential backoff retries."""
    for attempt in range(MAX_RETRIES):
        try:
            await asyncio.sleep(SLEEP_BETWEEN_CALLS)
            response = await client.get(url, params=params, timeout=60.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            wait = 2 ** attempt
            if attempt < MAX_RETRIES - 1:
                print(f"    Retry {attempt + 1}/{MAX_RETRIES} for {description}: {e}")
                print(f"    Waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"    FAILED after {MAX_RETRIES} attempts for {description}: {e}")
                return None
    return None


async def download_oz_tracts_for_state(client: httpx.AsyncClient, fips: str,
                                        state: str) -> list:
    """Download all OZ tracts for a single state, handling pagination."""
    all_features = []
    offset = 0

    while True:
        params = {
            "where": f"STATE='{fips}'",
            "outFields": "GEOID10,STATE,COUNTY,TRACT,STUSAB,STATE_NAME",
            "f": "geojson",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultOffset": str(offset),
            "resultRecordCount": str(BATCH_SIZE),
        }
        data = await fetch_with_retry(
            client, OZ_FEATURE_SERVICE, params,
            f"{state} OZ tracts (offset {offset})"
        )

        if not data or "features" not in data:
            break

        features = data["features"]
        if not features:
            break

        # Add OZ_VERSION to each feature
        for f in features:
            if f.get("properties"):
                f["properties"]["OZ_VERSION"] = "1.0"

        all_features.extend(features)
        print(f"      Fetched {len(features)} tracts (total: {len(all_features)})")

        # Check if there are more records
        if len(features) < BATCH_SIZE:
            break
        offset += BATCH_SIZE

    return all_features


async def main():
    """Download all OZ 1.0 tracts and write to NDJSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "national_oz_tracts.ndjson"

    # Determine which states to process
    if len(sys.argv) > 1:
        states_to_process = {s.upper(): STATE_FIPS[s.upper()]
                            for s in sys.argv[1:] if s.upper() in STATE_FIPS}
        if not states_to_process:
            print(f"ERROR: No valid state codes provided. Valid: {', '.join(sorted(STATE_FIPS.keys()))}")
            sys.exit(1)
    else:
        states_to_process = STATE_FIPS

    print("=" * 60)
    print("Opportunity Zones 1.0 - Download")
    print("=" * 60)
    print(f"Source: HUD ArcGIS Feature Service")
    print(f"States: {len(states_to_process)}")
    print(f"Output: {output_path}")
    print()

    all_features = []

    async with httpx.AsyncClient() as client:
        # First, try a quick count to verify the service is working
        count_params = {"where": "1=1", "returnCountOnly": "true", "f": "json"}
        count_data = await fetch_with_retry(
            client, OZ_FEATURE_SERVICE, count_params, "total count"
        )
        if count_data and "count" in count_data:
            print(f"Total OZ tracts in service: {count_data['count']}")
        print()

        for state, fips in sorted(states_to_process.items()):
            print(f"  [{state}] Downloading OZ tracts (FIPS: {fips})...")
            features = await download_oz_tracts_for_state(client, fips, state)
            if features:
                all_features.extend(features)
                print(f"  [{state}] Done: {len(features)} OZ tracts")
            else:
                print(f"  [{state}] No OZ tracts found")
            print()

    print(f"Total features collected: {len(all_features)}")

    # Write NDJSON (one GeoJSON feature per line)
    print(f"Writing NDJSON to {output_path}...")
    with open(output_path, "w") as f:
        for feature in all_features:
            f.write(json.dumps(feature) + "\n")

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Done! {len(all_features)} features, {file_size_mb:.1f} MB")
    print()

    # Validate
    if len(all_features) < 8000:
        print(f"WARNING: Expected ~8,764 OZ tracts but only got {len(all_features)}.")
        print("Some states may have failed. Check output above for errors.")
    else:
        print(f"SUCCESS: {len(all_features)} OZ tracts downloaded (expected ~8,764)")


if __name__ == "__main__":
    asyncio.run(main())
