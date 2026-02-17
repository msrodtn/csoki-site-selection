#!/usr/bin/env python3
"""
Download OZ 2.0 eligible census tracts from the EIG (Economic Innovation Group)
ArcGIS dashboard and Census TIGERweb for geometries.

Usage:
    python scripts/download_oz2_eligible.py
    python scripts/download_oz2_eligible.py TN CA TX   # specific states only

Output:
    mapbox-tilesets/national_oz2_eligible.ndjson

Data Sources:
    - EIG OZ 2.0 Eligibility: ArcGIS dashboard feature service
      https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/
    - Census TIGERweb: tract polygon geometries
      https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/8

Notes:
    - These are ELIGIBLE tracts, not final designations
    - Final OZ 2.0 will be designated by Treasury after Fall 2026
    - Excludes tracts already designated under OZ 1.0
"""

import httpx
import asyncio
import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "mapbox-tilesets"
OZ1_PATH = OUTPUT_DIR / "national_oz_tracts.ndjson"

# Census TIGERweb for tract geometries (2020 tracts)
TIGER_TRACTS_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_ACS2021/MapServer/8/query"
)

# EIG OZ 2.0 eligible tracts feature service
# This URL may need updating - EIG publishes via ArcGIS Online
EIG_ELIGIBLE_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/"
    "Opportunity_Zones_Eligible_Tracts_2026/FeatureServer/0/query"
)

# Fallback: If the EIG feature service URL changes, try the Census ACS
# low-income community tract data directly
CENSUS_LIC_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_ACS2021/MapServer/8/query"
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


async def download_eligible_tracts_eig(client: httpx.AsyncClient, fips: str,
                                        state: str) -> list:
    """Try downloading eligible tracts from EIG feature service."""
    all_features = []
    offset = 0

    while True:
        params = {
            "where": f"STATE='{fips}'",
            "outFields": "GEOID,STATE,COUNTY,TRACT,STATE_NAME,ELIGIBLE_STATUS",
            "f": "geojson",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultOffset": str(offset),
            "resultRecordCount": str(BATCH_SIZE),
        }
        data = await fetch_with_retry(
            client, EIG_ELIGIBLE_URL, params,
            f"{state} eligible tracts (offset {offset})"
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


async def download_tract_geometries_tiger(client: httpx.AsyncClient, fips: str,
                                           state: str) -> list:
    """Download all census tract geometries for a state from TIGERweb."""
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
            client, TIGER_TRACTS_URL, params,
            f"{state} tract geometries (offset {offset})"
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
    """Download OZ 2.0 eligible tracts and write to NDJSON."""
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
    print("Opportunity Zones 2.0 - Eligible Tracts Download")
    print("=" * 60)
    print(f"States: {len(states_to_process)}")
    print(f"Output: {output_path}")
    print()

    # Load OZ 1.0 GEOIDs to exclude
    oz1_geoids = load_oz1_geoids()
    print()

    all_features = []
    eig_available = True

    async with httpx.AsyncClient() as client:
        # Try EIG service first for the first state to check availability
        first_state = sorted(states_to_process.keys())[0]
        first_fips = states_to_process[first_state]
        print(f"Testing EIG feature service availability...")
        test_features = await download_eligible_tracts_eig(
            client, first_fips, first_state
        )

        if test_features:
            print(f"  EIG service available! Found {len(test_features)} for {first_state}")
            # Filter out OZ 1.0 tracts
            filtered = [f for f in test_features
                       if f.get("properties", {}).get("GEOID", "") not in oz1_geoids]
            for f in filtered:
                f["properties"]["ELIGIBLE_STATUS"] = f["properties"].get("ELIGIBLE_STATUS", "eligible")
            all_features.extend(filtered)
            print(f"  After excluding OZ 1.0: {len(filtered)} eligible tracts")
            print()

            # Continue with remaining states
            remaining_states = {k: v for k, v in states_to_process.items()
                               if k != first_state}
            for state, fips in sorted(remaining_states.items()):
                print(f"  [{state}] Downloading eligible tracts...")
                features = await download_eligible_tracts_eig(client, fips, state)
                if features:
                    filtered = [f for f in features
                               if f.get("properties", {}).get("GEOID", "") not in oz1_geoids]
                    for f in filtered:
                        f["properties"]["ELIGIBLE_STATUS"] = f["properties"].get("ELIGIBLE_STATUS", "eligible")
                    all_features.extend(filtered)
                    print(f"  [{state}] {len(filtered)} eligible tracts (excluded {len(features) - len(filtered)} OZ 1.0)")
                else:
                    print(f"  [{state}] No eligible tracts found")
        else:
            eig_available = False
            print("  EIG service not available. Will need manual CSV import.")
            print()
            print("  To use EIG data manually:")
            print("  1. Visit: https://arcgis.com/apps/dashboards/c473c71f0704408f934fbdc342caf1f1")
            print("  2. Export CSV of eligible tracts")
            print("  3. Place at: scripts/data/oz2_eligible_tracts.csv")
            print("  4. Re-run this script")
            print()

            # Check for manual CSV
            csv_path = Path(__file__).parent / "data" / "oz2_eligible_tracts.csv"
            if csv_path.exists():
                print(f"  Found manual CSV at {csv_path}")
                print("  Processing CSV + fetching geometries from TIGERweb...")
                # Read CSV GEOIDs
                import csv
                eligible_geoids = set()
                with open(csv_path) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        geoid = row.get("GEOID", row.get("geoid", row.get("GEOID10", "")))
                        if geoid and geoid not in oz1_geoids:
                            eligible_geoids.add(geoid)
                print(f"  {len(eligible_geoids)} eligible GEOIDs from CSV (excluding OZ 1.0)")

                # Fetch geometries from TIGERweb
                for state, fips in sorted(states_to_process.items()):
                    print(f"  [{state}] Fetching tract geometries...")
                    tracts = await download_tract_geometries_tiger(client, fips, state)
                    matched = [t for t in tracts
                              if t.get("properties", {}).get("GEOID", "") in eligible_geoids]
                    for f in matched:
                        f["properties"]["ELIGIBLE_STATUS"] = "eligible"
                        f["properties"]["STATE_NAME"] = state
                    all_features.extend(matched)
                    if matched:
                        print(f"  [{state}] {len(matched)} eligible tracts matched")
            else:
                print(f"  No manual CSV found at {csv_path}")
                print("  Exiting. Please provide EIG data.")
                sys.exit(1)

    print()
    print(f"Total eligible features: {len(all_features)}")

    # Write NDJSON
    print(f"Writing NDJSON to {output_path}...")
    with open(output_path, "w") as f:
        for feature in all_features:
            f.write(json.dumps(feature) + "\n")

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Done! {len(all_features)} features, {file_size_mb:.1f} MB")

    if not eig_available:
        print()
        print("NOTE: Used manual CSV import. When EIG updates their service,")
        print("re-run this script to get the latest eligibility data.")


if __name__ == "__main__":
    asyncio.run(main())
