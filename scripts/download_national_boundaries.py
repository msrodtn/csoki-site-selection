#!/usr/bin/env python3
"""
Download boundary + demographic data for all 50 states + DC (excluding Iowa)
for Mapbox tilesets.

Usage:
    python scripts/download_national_boundaries.py

Output:
    mapbox-tilesets/states/{ST}_counties.geojson
    mapbox-tilesets/states/{ST}_cities.geojson
    mapbox-tilesets/states/{ST}_zctas.geojson
    mapbox-tilesets/states/{ST}_tracts.geojson

Data Sources:
    - ArcGIS Living Atlas for counties & tracts (demographics + geometry)
    - Census TIGER for cities & ZCTAs (boundaries only)
    - Census ACS API for city & ZCTA population
"""

import httpx
import asyncio
import json
import sys
import time
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "mapbox-tilesets" / "states"

# ArcGIS Living Atlas - has demographics + boundaries
ACS_POP_URL = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Total_Population_Boundaries/FeatureServer"
ACS_INC_URL = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Median_Income_by_Race_and_Age_Selp_Emp_Boundaries/FeatureServer"

# Census TIGER - for cities and ZCTAs (boundaries only)
TIGER_BASE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer"

# All 50 states + DC FIPS codes (excluding Iowa "19")
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
    "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
    "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
    "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50",
    "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
}

# State bounding boxes for ZCTA spatial queries
STATE_BBOXES = {
    "AL": "-88.5,30.1,-84.9,35.0",
    "AK": "-179.2,51.2,-129.0,71.4",
    "AZ": "-114.8,31.3,-109.0,37.0",
    "AR": "-94.6,33.0,-89.6,36.5",
    "CA": "-124.5,32.5,-114.1,42.0",
    "CO": "-109.1,36.9,-102.0,41.0",
    "CT": "-73.7,41.0,-71.8,42.1",
    "DE": "-75.8,38.4,-75.0,39.8",
    "DC": "-77.1,38.8,-76.9,39.0",
    "FL": "-87.6,24.4,-80.0,31.0",
    "GA": "-85.6,30.4,-80.8,35.0",
    "HI": "-160.3,18.9,-154.8,22.3",
    "ID": "-117.3,41.9,-111.0,49.1",
    "IL": "-91.5,36.9,-87.0,42.5",
    "IN": "-88.1,37.8,-84.8,41.8",
    "KS": "-102.1,36.9,-94.6,40.0",
    "KY": "-89.6,36.5,-81.9,39.2",
    "LA": "-94.1,28.9,-88.8,33.0",
    "ME": "-71.1,43.0,-66.9,47.5",
    "MD": "-79.5,37.9,-75.0,39.7",
    "MA": "-73.5,41.2,-69.9,42.9",
    "MI": "-90.4,41.7,-82.1,48.3",
    "MN": "-97.3,43.5,-89.5,49.4",
    "MS": "-91.7,30.1,-88.1,35.0",
    "MO": "-95.8,36.0,-89.1,40.6",
    "MT": "-116.1,44.4,-104.0,49.0",
    "NE": "-104.1,39.9,-95.3,43.1",
    "NV": "-120.1,35.0,-114.0,42.1",
    "NH": "-72.6,42.7,-70.7,45.3",
    "NJ": "-75.6,38.9,-73.9,41.4",
    "NM": "-109.1,31.3,-103.0,37.0",
    "NY": "-79.8,40.5,-71.9,45.0",
    "NC": "-84.3,33.8,-75.5,36.6",
    "ND": "-104.1,45.9,-96.6,49.0",
    "OH": "-84.8,38.4,-80.5,42.0",
    "OK": "-103.0,33.6,-94.4,37.0",
    "OR": "-124.6,41.9,-116.5,46.3",
    "PA": "-80.5,39.7,-74.7,42.3",
    "RI": "-71.9,41.1,-71.1,42.0",
    "SC": "-83.4,32.0,-78.5,35.2",
    "SD": "-104.1,42.5,-96.4,46.0",
    "TN": "-90.3,35.0,-81.6,36.7",
    "TX": "-106.7,25.8,-93.5,36.5",
    "UT": "-114.1,37.0,-109.0,42.0",
    "VT": "-73.4,42.7,-71.5,45.0",
    "VA": "-83.7,36.5,-75.2,39.5",
    "WA": "-124.8,45.5,-116.9,49.0",
    "WV": "-82.6,37.2,-77.7,40.6",
    "WI": "-92.9,42.5,-86.2,47.1",
    "WY": "-111.1,40.9,-104.1,45.0",
}

# sq meters to sq miles conversion
SQ_METERS_PER_SQ_MILE = 2589988.0

# Rate limiting
SLEEP_BETWEEN_CALLS = 1.0
MAX_RETRIES = 3


async def fetch_with_retry(client: httpx.AsyncClient, url: str, params: dict,
                           description: str):
    """Fetch URL with exponential backoff retries."""
    for attempt in range(MAX_RETRIES):
        try:
            await asyncio.sleep(SLEEP_BETWEEN_CALLS)
            response = await client.get(url, params=params)
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


async def download_counties(client: httpx.AsyncClient, fips: str, state: str) -> dict:
    """Download county boundaries + population + income for a state."""
    print(f"    Fetching counties...")
    # Population + geometry
    url = f"{ACS_POP_URL}/1/query"
    params = {
        "where": f"GEOID LIKE '{fips}%'",
        "outFields": "NAME,GEOID,B01001_001E,Shape__Area",
        "f": "geojson",
        "returnGeometry": "true",
        "outSR": "4326",
    }
    data = await fetch_with_retry(client, url, params, f"{state} counties")
    if not data or "features" not in data:
        return {"type": "FeatureCollection", "features": []}

    # Income
    inc_url = f"{ACS_INC_URL}/1/query"
    inc_params = {
        "where": f"GEOID LIKE '{fips}%'",
        "outFields": "GEOID,B19049_001E",
        "f": "json",
        "returnGeometry": "false",
    }
    inc_data = await fetch_with_retry(client, inc_url, inc_params, f"{state} county income")
    income_lookup = {}
    if inc_data and "features" in inc_data:
        income_lookup = {
            f["attributes"]["GEOID"]: f["attributes"].get("B19049_001E", 0)
            for f in inc_data["features"]
        }

    # Process features
    for feature in data.get("features", []):
        props = feature["properties"]
        geoid = props.get("GEOID", "")
        pop = props.pop("B01001_001E", 0) or 0
        props["POPULATION"] = pop
        props["MEDIAN_INCOME"] = income_lookup.get(geoid, 0)
        shape_area = props.pop("Shape__Area", None)
        if shape_area and shape_area > 0:
            area_sq_miles = shape_area / SQ_METERS_PER_SQ_MILE
            props["POP_DENSITY"] = round(pop / area_sq_miles, 1) if area_sq_miles > 0 else 0
        else:
            props["POP_DENSITY"] = 0

    return data


async def download_cities(client: httpx.AsyncClient, fips: str, state: str,
                          city_pop_lookup: dict) -> dict:
    """Download city boundaries + population for a state."""
    print(f"    Fetching cities...")
    url = f"{TIGER_BASE}/24/query"
    params = {
        "where": f"STATE = '{fips}'",
        "outFields": "NAME,GEOID,STATE,ALAND",
        "f": "geojson",
        "returnGeometry": "true",
        "outSR": "4326",
    }
    data = await fetch_with_retry(client, url, params, f"{state} cities")
    if not data or "features" not in data:
        return {"type": "FeatureCollection", "features": []}

    for feature in data.get("features", []):
        props = feature["properties"]
        geoid = props.get("GEOID", "")
        props["POPULATION"] = city_pop_lookup.get(geoid, 0)

    return data


async def download_zctas(client: httpx.AsyncClient, bbox: str, state: str,
                         zcta_pop_lookup: dict) -> dict:
    """Download ZCTA boundaries for a state using bounding box."""
    print(f"    Fetching ZCTAs...")
    url = f"{TIGER_BASE}/0/query"
    minX, minY, maxX, maxY = bbox.split(",")
    params = {
        "where": "1=1",
        "geometry": f"{minX},{minY},{maxX},{maxY}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "NAME,GEOID20,ZCTA5CE20,ALAND20",
        "f": "geojson",
        "returnGeometry": "true",
        "outSR": "4326",
    }
    data = await fetch_with_retry(client, url, params, f"{state} ZCTAs")
    if not data or "features" not in data:
        return {"type": "FeatureCollection", "features": []}

    for feature in data.get("features", []):
        props = feature["properties"]
        zcta_code = props.get("ZCTA5CE20") or props.get("GEOID20") or ""
        props["POPULATION"] = zcta_pop_lookup.get(zcta_code, 0)

    return data


async def download_tracts(client: httpx.AsyncClient, fips: str, state: str) -> dict:
    """Download tract boundaries + population + income for a state (paginated)."""
    print(f"    Fetching tracts (paginated)...")
    url = f"{ACS_POP_URL}/2/query"

    all_features = []
    offset = 0
    batch_size = 500

    while True:
        params = {
            "where": f"GEOID LIKE '{fips}%'",
            "outFields": "NAME,GEOID,B01001_001E,Shape__Area",
            "f": "geojson",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultOffset": str(offset),
            "resultRecordCount": str(batch_size),
        }
        data = await fetch_with_retry(client, url, params,
                                      f"{state} tracts (offset {offset})")
        if not data:
            break

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        print(f"      {len(all_features)} tracts so far...")

        if len(features) < batch_size:
            break

        offset += batch_size

    # Fetch income
    inc_url = f"{ACS_INC_URL}/2/query"
    tract_income = {}
    inc_offset = 0
    while True:
        inc_params = {
            "where": f"GEOID LIKE '{fips}%'",
            "outFields": "GEOID,B19049_001E",
            "f": "json",
            "returnGeometry": "false",
            "resultOffset": str(inc_offset),
            "resultRecordCount": str(batch_size),
        }
        inc_data = await fetch_with_retry(client, inc_url, inc_params,
                                          f"{state} tract income (offset {inc_offset})")
        if not inc_data:
            break

        inc_features = inc_data.get("features", [])
        if not inc_features:
            break

        for f in inc_features:
            tract_income[f["attributes"]["GEOID"]] = f["attributes"].get("B19049_001E", 0)

        if len(inc_features) < batch_size:
            break
        inc_offset += batch_size

    # Process features
    for feature in all_features:
        props = feature["properties"]
        geoid = props.get("GEOID", "")
        pop = props.pop("B01001_001E", 0) or 0
        props["POPULATION"] = pop
        props["MEDIAN_INCOME"] = tract_income.get(geoid, 0)
        shape_area = props.pop("Shape__Area", None)
        if shape_area and shape_area > 0:
            area_sq_miles = shape_area / SQ_METERS_PER_SQ_MILE
            props["POP_DENSITY"] = round(pop / area_sq_miles, 1) if area_sq_miles > 0 else 0
        else:
            props["POP_DENSITY"] = 0

    return {"type": "FeatureCollection", "features": all_features}


async def download_national_city_population() -> dict:
    """Download city population for all states from Census ACS API."""
    print("Fetching national city population from Census ACS...")
    url = "https://api.census.gov/data/2022/acs/acs5"
    result = {}

    async with httpx.AsyncClient(timeout=120.0) as client:
        for state_abbr, fips in STATE_FIPS.items():
            params = {
                "get": "NAME,B01001_001E",
                "for": "place:*",
                "in": f"state:{fips}",
            }
            data = await fetch_with_retry(client, url, params,
                                          f"{state_abbr} city population")
            if data and len(data) > 1:
                for row in data[1:]:  # Skip header
                    name, pop, state_code, place = row
                    geoid = f"{state_code}{place}"
                    try:
                        result[geoid] = int(pop) if pop else 0
                    except (ValueError, TypeError):
                        result[geoid] = 0
            print(f"  {state_abbr}: {len(data) - 1 if data and len(data) > 1 else 0} cities")

    print(f"  Total: {len(result)} city population records")
    return result


async def download_national_zcta_population() -> dict:
    """Download ZCTA population nationally (single request)."""
    print("Fetching national ZCTA population from Census ACS...")
    url = "https://api.census.gov/data/2022/acs/acs5"
    params = {
        "get": "NAME,B01001_001E",
        "for": "zip code tabulation area:*",
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        data = await fetch_with_retry(client, url, params, "national ZCTA population")

    if not data or len(data) < 2:
        print("  WARNING: Failed to fetch national ZCTA population")
        return {}

    result = {}
    for row in data[1:]:  # Skip header
        name, pop, zcta = row
        try:
            result[zcta] = int(pop) if pop else 0
        except (ValueError, TypeError):
            result[zcta] = 0

    print(f"  Total: {len(result)} ZCTA population records")
    return result


def save_geojson(data: dict, filepath: Path) -> int:
    """Save GeoJSON data and return feature count."""
    with open(filepath, "w") as f:
        json.dump(data, f)
    return len(data.get("features", []))


async def process_state(client: httpx.AsyncClient, state: str, fips: str,
                        city_pop: dict, zcta_pop: dict) -> dict:
    """Download all 4 boundary types for a single state."""
    bbox = STATE_BBOXES[state]
    results = {}

    # Counties
    county_file = OUTPUT_DIR / f"{state}_counties.geojson"
    if county_file.exists():
        print(f"    Skipping counties (already exists)")
    else:
        counties = await download_counties(client, fips, state)
        count = save_geojson(counties, county_file)
        results["counties"] = count
        print(f"    -> {count} counties saved")

    # Cities
    city_file = OUTPUT_DIR / f"{state}_cities.geojson"
    if city_file.exists():
        print(f"    Skipping cities (already exists)")
    else:
        cities = await download_cities(client, fips, state, city_pop)
        count = save_geojson(cities, city_file)
        results["cities"] = count
        print(f"    -> {count} cities saved")

    # ZCTAs
    zcta_file = OUTPUT_DIR / f"{state}_zctas.geojson"
    if zcta_file.exists():
        print(f"    Skipping ZCTAs (already exists)")
    else:
        zctas = await download_zctas(client, bbox, state, zcta_pop)
        count = save_geojson(zctas, zcta_file)
        results["zctas"] = count
        print(f"    -> {count} ZCTAs saved")

    # Tracts
    tract_file = OUTPUT_DIR / f"{state}_tracts.geojson"
    if tract_file.exists():
        print(f"    Skipping tracts (already exists)")
    else:
        tracts = await download_tracts(client, fips, state)
        count = save_geojson(tracts, tract_file)
        results["tracts"] = count
        print(f"    -> {count} tracts saved")

    return results


async def main(state_filter=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    states = state_filter if state_filter else sorted(STATE_FIPS.keys())
    # Validate state filter
    for s in states:
        if s not in STATE_FIPS:
            print(f"ERROR: Unknown state '{s}'. Valid: {', '.join(sorted(STATE_FIPS.keys()))}")
            return

    label = f"Worker ({states[0]}-{states[-1]})" if state_filter else "Full Download"
    print("=" * 60)
    print(f"National Boundary Download - {label}")
    print(f"States: {', '.join(states)} ({len(states)} total)")
    print("=" * 60)

    # Step 1: Download national population lookups first
    # Use cached files if another worker already fetched them
    cache_dir = OUTPUT_DIR / "_cache"
    cache_dir.mkdir(exist_ok=True)
    zcta_cache = cache_dir / "zcta_pop.json"
    city_cache = cache_dir / "city_pop.json"

    if zcta_cache.exists():
        print("\n  Loading cached ZCTA population...")
        with open(zcta_cache) as f:
            zcta_pop = json.load(f)
        print(f"  Loaded {len(zcta_pop)} ZCTA records from cache")
    else:
        print("\n--- PHASE 1: National Population Lookups ---\n")
        zcta_pop = await download_national_zcta_population()
        with open(zcta_cache, "w") as f:
            json.dump(zcta_pop, f)

    if city_cache.exists():
        print("  Loading cached city population...")
        with open(city_cache) as f:
            city_pop = json.load(f)
        print(f"  Loaded {len(city_pop)} city records from cache")
    else:
        city_pop = await download_national_city_population()
        with open(city_cache, "w") as f:
            json.dump(city_pop, f)

    # Step 2: Process each state sequentially
    print(f"\n--- PHASE 2: State Boundary Downloads ({len(states)} states) ---\n")
    total_states = len(states)
    summary = {}

    async with httpx.AsyncClient(timeout=180.0) as client:
        for i, state in enumerate(states, 1):
            fips = STATE_FIPS[state]
            print(f"\n[{i}/{total_states}] Processing {state} (FIPS: {fips})")
            print("-" * 40)

            start = time.time()
            results = await process_state(client, state, fips, city_pop, zcta_pop)
            elapsed = time.time() - start

            summary[state] = results
            print(f"    Completed in {elapsed:.1f}s")

    # Print summary
    print("\n" + "=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)

    total_files = 0
    for state in sorted(summary.keys()):
        s = summary[state]
        if s:
            parts = ", ".join(f"{k}: {v}" for k, v in s.items())
            print(f"  {state}: {parts}")
            total_files += len(s)

    skipped = total_states * 4 - total_files
    print(f"\n  New files: {total_files}")
    print(f"  Skipped (already existed): {skipped}")
    print(f"  Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    # Support: python script.py AL AK AZ  (specific states)
    #          python script.py             (all states)
    state_args = [s.upper() for s in sys.argv[1:]] if len(sys.argv) > 1 else None
    asyncio.run(main(state_args))
