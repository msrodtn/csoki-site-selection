#!/usr/bin/env python3
"""
Add population data to Cities and ZCTAs GeoJSON files.

This script:
1. Fetches population data from Census ACS API
2. Merges it with existing boundary GeoJSON files
3. Outputs new GeoJSON files ready for Mapbox upload

After running, upload to Mapbox with:
  mapbox tilesets upload msrodtn.9jpdhu14 mapbox-tilesets/cities_with_pop.geojson --name "Cities with Population"
  mapbox tilesets upload msrodtn.917bnr7e mapbox-tilesets/zctas_with_pop.geojson --name "ZCTAs with Population"
"""

import json
import httpx
import asyncio
from pathlib import Path

# Census API base URL (no key required for basic queries)
CENSUS_API_BASE = "https://api.census.gov/data/2022/acs/acs5"

# State FIPS codes
STATE_FIPS = {
    "IA": "19",
    "NE": "31",
    "NV": "32",
    "ID": "16",
}


async def fetch_city_population(state_fips: str) -> dict:
    """Fetch population for all places (cities) in a state from Census ACS."""
    url = f"{CENSUS_API_BASE}"
    params = {
        "get": "NAME,B01001_001E",  # NAME and Total Population
        "for": "place:*",
        "in": f"state:{state_fips}",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # First row is headers: ['NAME', 'B01001_001E', 'state', 'place']
        # Convert to dict keyed by GEOID (state + place FIPS)
        result = {}
        for row in data[1:]:  # Skip header
            name, pop, state, place = row
            geoid = f"{state}{place}"  # Full GEOID for places
            try:
                result[geoid] = int(pop) if pop else 0
            except (ValueError, TypeError):
                result[geoid] = 0
        return result


async def fetch_zcta_population() -> dict:
    """Fetch population for all ZCTAs from Census ACS."""
    url = f"{CENSUS_API_BASE}"
    params = {
        "get": "NAME,B01001_001E",  # NAME and Total Population
        "for": "zip code tabulation area:*",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # First row is headers: ['NAME', 'B01001_001E', 'zip code tabulation area']
        # Convert to dict keyed by ZCTA
        result = {}
        for row in data[1:]:  # Skip header
            name, pop, zcta = row
            try:
                result[zcta] = int(pop) if pop else 0
            except (ValueError, TypeError):
                result[zcta] = 0
        return result


async def add_population_to_cities():
    """Add population data to cities.geojson."""
    print("Fetching city population data from Census ACS...")

    # Fetch population for all target states
    all_populations = {}
    for state, fips in STATE_FIPS.items():
        print(f"  Fetching {state} ({fips})...")
        try:
            state_pops = await fetch_city_population(fips)
            all_populations.update(state_pops)
            print(f"    Found {len(state_pops)} cities")
        except Exception as e:
            print(f"    Error fetching {state}: {e}")

    print(f"Total city populations fetched: {len(all_populations)}")

    # Load existing cities GeoJSON
    cities_path = Path("mapbox-tilesets/cities.geojson")
    with open(cities_path) as f:
        cities = json.load(f)

    # Add population to each feature
    matched = 0
    for feature in cities["features"]:
        props = feature["properties"]
        geoid = props.get("GEOID", "")

        if geoid in all_populations:
            props["POPULATION"] = all_populations[geoid]
            matched += 1
        else:
            props["POPULATION"] = 0

    print(f"Matched {matched} of {len(cities['features'])} cities with population data")

    # Save updated GeoJSON
    output_path = Path("mapbox-tilesets/cities_with_pop.geojson")
    with open(output_path, "w") as f:
        json.dump(cities, f)

    print(f"Saved to {output_path}")
    return output_path


async def add_population_to_zctas():
    """Add population data to zctas.geojson."""
    print("\nFetching ZCTA population data from Census ACS...")

    try:
        zcta_pops = await fetch_zcta_population()
        print(f"Total ZCTA populations fetched: {len(zcta_pops)}")
    except Exception as e:
        print(f"Error fetching ZCTA data: {e}")
        return None

    # Load existing ZCTAs GeoJSON
    zctas_path = Path("mapbox-tilesets/zctas.geojson")
    with open(zctas_path) as f:
        zctas = json.load(f)

    # Add population to each feature
    matched = 0
    for feature in zctas["features"]:
        props = feature["properties"]
        # ZCTA can be in ZCTA5CE20, GEOID20, or as the last 5 digits of GEOID
        zcta_code = props.get("ZCTA5CE20") or props.get("GEOID20") or ""

        if zcta_code in zcta_pops:
            props["POPULATION"] = zcta_pops[zcta_code]
            matched += 1
        else:
            props["POPULATION"] = 0

    print(f"Matched {matched} of {len(zctas['features'])} ZCTAs with population data")

    # Save updated GeoJSON
    output_path = Path("mapbox-tilesets/zctas_with_pop.geojson")
    with open(output_path, "w") as f:
        json.dump(zctas, f)

    print(f"Saved to {output_path}")
    return output_path


async def main():
    print("=" * 60)
    print("Adding Population Data to Boundary Tilesets")
    print("=" * 60)

    # Change to project root
    import os
    script_dir = Path(__file__).parent
    os.chdir(script_dir.parent)

    # Process cities
    cities_output = await add_population_to_cities()

    # Process ZCTAs
    zctas_output = await add_population_to_zctas()

    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("\n1. Install Mapbox CLI if not already installed:")
    print("   npm install -g @mapbox/mapbox-cli")
    print("\n2. Upload the new tilesets (replaces existing):")
    if cities_output:
        print(f"   mapbox tilesets upload msrodtn.9jpdhu14 {cities_output} --name 'Cities with Population'")
    if zctas_output:
        print(f"   mapbox tilesets upload msrodtn.917bnr7e {zctas_output} --name 'ZCTAs with Population'")
    print("\n3. Check Mapbox Studio for the new source-layer names")
    print("4. Update BOUNDARY_TILESETS in MapboxMap.tsx if source-layer names changed")


if __name__ == "__main__":
    asyncio.run(main())
