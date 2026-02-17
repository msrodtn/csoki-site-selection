#!/usr/bin/env python3
"""
Download OZ 2.0 eligible census tracts from HUD Qualified Census Tracts 2026
ArcGIS feature service (includes polygon geometries).

Usage:
    python scripts/download_oz2_eligible.py
    python scripts/download_oz2_eligible.py TN CA TX   # specific states only

Output:
    mapbox-tilesets/national_oz2_eligible.ndjson

Data Sources:
    - HUD Qualified Census Tracts 2026:
      https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/QUALIFIED_CENSUS_TRACTS_2026/FeatureServer/0
    - OZ 1.0 designated tracts (excluded from output):
      mapbox-tilesets/national_oz_tracts.ndjson

Notes:
    - QCT 2026 tracts are the eligible pool for OZ 2.0 designation
    - Tracts already designated under OZ 1.0 are excluded
    - Final OZ 2.0 will be designated by Treasury after Fall 2026
"""

import httpx
import asyncio
import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "mapbox-tilesets"
OZ1_PATH = OUTPUT_DIR / "national_oz_tracts.ndjson"

# HUD Qualified Census Tracts 2026 - the eligible pool for OZ 2.0 designation
# These are tracts where >=50% of households earn <60% of AMGI or poverty rate >25%
# Service has polygon geometries, so no need for TIGERweb
QCT_2026_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/"
    "QUALIFIED_CENSUS_TRACTS_2026/FeatureServer/0/query"
)

# State FIPS codes
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
    "WV": "54", "WI": "55", "WY": "56",
}

FIPS_TO_STATE = {v: k for k, v in STATE_FIPS.items()}

SLEEP_BETWEEN_CALLS = 0.5
MAX_RETRIES = 3
BATCH_SIZE = 500


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


def load_oz1_geoids() -> set:
    """Load existing OZ 1.0 GEOIDs to exclude from eligible list."""
    oz1_geoids = set()
    if OZ1_PATH.exists():
        print(f"Loading OZ 1.0 GEOIDs from {OZ1_PATH}...")
        with open(OZ1_PATH) as f:
            for line in f:
                try:
                    feature = json.loads(line.strip())
                    geoid = feature.get("properties", {}).get("GEOID10", "")
                    if geoid:
                        oz1_geoids.add(geoid)
                except json.JSONDecodeError:
                    continue
        print(f"  Loaded {len(oz1_geoids)} OZ 1.0 GEOIDs to exclude")
    else:
        print(f"WARNING: OZ 1.0 file not found at {OZ1_PATH}")
        print("  Run download_opportunity_zones.py first to exclude designated tracts")
    return oz1_geoids


async def download_qct_tracts(client: httpx.AsyncClient, fips: str,
                              state: str) -> list:
    """Download QCT 2026 tracts for a state from HUD feature service."""
    all_features = []
    offset = 0

    while True:
        params = {
            "where": f"STATE='{fips}'",
            "outFields": "GEOID,STATE,COUNTY,TRACT,NAME",
            "f": "geojson",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultOffset": str(offset),
            "resultRecordCount": str(BATCH_SIZE),
        }
        data = await fetch_with_retry(
            client, QCT_2026_URL, params,
            f"{state} QCT tracts (offset {offset})"
        )

        if not data or "features" not in data:
            break

        features = data["features"]
        if not features:
            break

        all_features.extend(features)

        if len(features) < BATCH_SIZE:
            break
        offset += BATCH_SIZE

    return all_features


async def main():
    """Download QCT 2026 eligible tracts and write to NDJSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "national_oz2_eligible.ndjson"

    # Determine which states to process
    if len(sys.argv) > 1:
        states_to_process = {s.upper(): STATE_FIPS[s.upper()]
                            for s in sys.argv[1:] if s.upper() in STATE_FIPS}
        if not states_to_process:
            print(f"ERROR: No valid state codes. Valid: {', '.join(sorted(STATE_FIPS.keys()))}")
            sys.exit(1)
    else:
        states_to_process = STATE_FIPS

    print("=" * 60)
    print("OZ 2.0 Eligible Tracts - HUD QCT 2026 Download")
    print("=" * 60)
    print(f"Source: HUD Qualified Census Tracts 2026")
    print(f"States: {len(states_to_process)}")
    print(f"Output: {output_path}")
    print()

    # Load OZ 1.0 GEOIDs to exclude
    oz1_geoids = load_oz1_geoids()
    print()

    all_features = []

    async with httpx.AsyncClient() as client:
        for state, fips in sorted(states_to_process.items()):
            print(f"  [{state}] Downloading QCT 2026 tracts...")
            features = await download_qct_tracts(client, fips, state)

            if features:
                # Exclude tracts already designated under OZ 1.0
                filtered = [f for f in features
                           if f.get("properties", {}).get("GEOID", "") not in oz1_geoids]

                # Add eligibility metadata
                for f in filtered:
                    f["properties"]["ELIGIBLE_STATUS"] = "qualified"
                    f["properties"]["STATE_NAME"] = state

                excluded = len(features) - len(filtered)
                all_features.extend(filtered)
                print(f"  [{state}] {len(filtered)} eligible tracts"
                      + (f" (excluded {excluded} OZ 1.0)" if excluded else ""))
            else:
                print(f"  [{state}] No tracts found")

    print()
    print(f"Total eligible features: {len(all_features)}")

    if not all_features:
        print("ERROR: No features downloaded. Check network connectivity.")
        sys.exit(1)

    # Write NDJSON
    print(f"Writing NDJSON to {output_path}...")
    with open(output_path, "w") as f:
        for feature in all_features:
            f.write(json.dumps(feature) + "\n")

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Done! {len(all_features)} features, {file_size_mb:.1f} MB")


if __name__ == "__main__":
    asyncio.run(main())
