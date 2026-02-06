#!/usr/bin/env python3
"""
Fallback: Download national city + ZCTA boundaries from Census Bureau
cartographic boundary shapefiles when the TIGER API is down.

Downloads static shapefile ZIPs, converts to GeoJSON, adds population,
and saves per-state files matching the download_national_boundaries.py format.

Usage:
    python scripts/download_cities_zctas_fallback.py

Requires: pip install shapefile (pyshp)
"""

import asyncio
import io
import json
import zipfile
from pathlib import Path

import httpx

try:
    import shapefile
except ImportError:
    print("ERROR: pyshp is required. Install with: pip install pyshp")
    raise SystemExit(1)

OUTPUT_DIR = Path(__file__).parent.parent / "mapbox-tilesets" / "states"
CACHE_DIR = OUTPUT_DIR / "_cache"

# Census Bureau cartographic boundary shapefiles
PLACES_URL = "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_place_500k.zip"
ZCTA_URL = "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_zcta520_500k.zip"

# State FIPS to abbreviation mapping
FIPS_TO_STATE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}

# State bounding boxes for ZCTA assignment
STATE_BBOXES = {
    "AL": (-88.5, 30.1, -84.9, 35.0), "AK": (-179.2, 51.2, -129.0, 71.4),
    "AZ": (-114.8, 31.3, -109.0, 37.0), "AR": (-94.6, 33.0, -89.6, 36.5),
    "CA": (-124.5, 32.5, -114.1, 42.0), "CO": (-109.1, 36.9, -102.0, 41.0),
    "CT": (-73.7, 41.0, -71.8, 42.1), "DE": (-75.8, 38.4, -75.0, 39.8),
    "DC": (-77.1, 38.8, -76.9, 39.0), "FL": (-87.6, 24.4, -80.0, 31.0),
    "GA": (-85.6, 30.4, -80.8, 35.0), "HI": (-160.3, 18.9, -154.8, 22.3),
    "ID": (-117.3, 41.9, -111.0, 49.1), "IL": (-91.5, 36.9, -87.0, 42.5),
    "IN": (-88.1, 37.8, -84.8, 41.8), "IA": (-96.7, 40.3, -90.1, 43.6),
    "KS": (-102.1, 36.9, -94.6, 40.0), "KY": (-89.6, 36.5, -81.9, 39.2),
    "LA": (-94.1, 28.9, -88.8, 33.0), "ME": (-71.1, 43.0, -66.9, 47.5),
    "MD": (-79.5, 37.9, -75.0, 39.7), "MA": (-73.5, 41.2, -69.9, 42.9),
    "MI": (-90.4, 41.7, -82.1, 48.3), "MN": (-97.3, 43.5, -89.5, 49.4),
    "MS": (-91.7, 30.1, -88.1, 35.0), "MO": (-95.8, 36.0, -89.1, 40.6),
    "MT": (-116.1, 44.4, -104.0, 49.0), "NE": (-104.1, 39.9, -95.3, 43.1),
    "NV": (-120.1, 35.0, -114.0, 42.1), "NH": (-72.6, 42.7, -70.7, 45.3),
    "NJ": (-75.6, 38.9, -73.9, 41.4), "NM": (-109.1, 31.3, -103.0, 37.0),
    "NY": (-79.8, 40.5, -71.9, 45.0), "NC": (-84.3, 33.8, -75.5, 36.6),
    "ND": (-104.1, 45.9, -96.6, 49.0), "OH": (-84.8, 38.4, -80.5, 42.0),
    "OK": (-103.0, 33.6, -94.4, 37.0), "OR": (-124.6, 41.9, -116.5, 46.3),
    "PA": (-80.5, 39.7, -74.7, 42.3), "RI": (-71.9, 41.1, -71.1, 42.0),
    "SC": (-83.4, 32.0, -78.5, 35.2), "SD": (-104.1, 42.5, -96.4, 46.0),
    "TN": (-90.3, 35.0, -81.6, 36.7), "TX": (-106.7, 25.8, -93.5, 36.5),
    "UT": (-114.1, 37.0, -109.0, 42.0), "VT": (-73.4, 42.7, -71.5, 45.0),
    "VA": (-83.7, 36.5, -75.2, 39.5), "WA": (-124.8, 45.5, -116.9, 49.0),
    "WV": (-82.6, 37.2, -77.7, 40.6), "WI": (-92.9, 42.5, -86.2, 47.1),
    "WY": (-111.1, 40.9, -104.1, 45.0),
}


def shapefile_to_geojson(sf):
    """Convert a pyshp Reader to a list of GeoJSON features."""
    features = []
    for sr in sf.shapeRecords():
        geom = sr.shape.__geo_interface__
        props = {}
        for i, field in enumerate(sf.fields[1:]):  # Skip DeletionFlag
            props[field[0]] = sr.record[i]
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props,
        })
    return features


def download_and_extract_shapefile(url, name):
    """Download a ZIP shapefile and return a pyshp Reader."""
    cache_file = CACHE_DIR / f"{name}.zip"
    if cache_file.exists():
        print(f"  Using cached {name}.zip")
        data = cache_file.read_bytes()
    else:
        print(f"  Downloading {name} ({url})...")
        r = httpx.get(url, timeout=300, follow_redirects=True)
        r.raise_for_status()
        data = r.content
        cache_file.write_bytes(data)
        print(f"  Downloaded {len(data) / 1024 / 1024:.1f} MB")

    zf = zipfile.ZipFile(io.BytesIO(data))
    # Find the .shp file
    shp_name = [n for n in zf.namelist() if n.endswith(".shp")][0]
    base = shp_name[:-4]

    shp_data = io.BytesIO(zf.read(base + ".shp"))
    dbf_data = io.BytesIO(zf.read(base + ".dbf"))
    shx_data = io.BytesIO(zf.read(base + ".shx"))

    return shapefile.Reader(shp=shp_data, dbf=dbf_data, shx=shx_data)


async def load_population_cache():
    """Load cached population lookups."""
    city_cache = CACHE_DIR / "city_pop.json"
    zcta_cache = CACHE_DIR / "zcta_pop.json"

    city_pop = {}
    zcta_pop = {}

    if city_cache.exists():
        with open(city_cache) as f:
            city_pop = json.load(f)
        print(f"  Loaded {len(city_pop)} city population records")
    else:
        print("  WARNING: No city population cache. Run download_national_boundaries.py first.")

    if zcta_cache.exists():
        with open(zcta_cache) as f:
            zcta_pop = json.load(f)
        print(f"  Loaded {len(zcta_pop)} ZCTA population records")
    else:
        print("  WARNING: No ZCTA population cache. Run download_national_boundaries.py first.")

    return city_pop, zcta_pop


def centroid(geometry):
    """Rough centroid of a geometry for state assignment."""
    if geometry["type"] == "Polygon":
        coords = geometry["coordinates"][0]
    elif geometry["type"] == "MultiPolygon":
        # Use the largest polygon
        largest = max(geometry["coordinates"], key=lambda p: len(p[0]))
        coords = largest[0]
    else:
        return None, None
    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return sum(lngs) / len(lngs), sum(lats) / len(lats)


# ZIP code 3-digit prefix to state mapping (USPS)
ZIP3_TO_STATE = {}
_zip3_map = {
    "AL": range(350, 370), "AK": [995, 996, 997, 998, 999],
    "AZ": range(850, 866), "AR": list(range(716, 730)) + [720, 721, 722, 723, 724, 725, 726, 727, 728, 729],
    "CA": list(range(900, 962)),
    "CO": range(800, 817), "CT": range(60, 70), "DE": range(197, 200),
    "DC": list(range(200, 206)) + [569], "FL": list(range(320, 350)),
    "GA": list(range(300, 320)) + [398, 399],
    "HI": range(967, 969), "ID": range(832, 839),
    "IL": list(range(600, 630)),
    "IN": list(range(460, 480)),
    "IA": list(range(500, 529)),
    "KS": list(range(660, 680)),
    "KY": list(range(400, 428)),
    "LA": list(range(700, 715)),
    "ME": list(range(39, 50)),
    "MD": list(range(206, 220)),
    "MA": list(range(10, 28)),
    "MI": list(range(480, 500)),
    "MN": list(range(550, 568)),
    "MS": list(range(386, 398)),
    "MO": list(range(630, 659)),
    "MT": list(range(590, 600)),
    "NE": list(range(680, 694)),
    "NV": list(range(889, 899)),
    "NH": list(range(30, 39)),
    "NJ": list(range(70, 90)),
    "NM": list(range(870, 885)),
    "NY": list(range(100, 150)),
    "NC": list(range(270, 290)),
    "ND": list(range(580, 589)),
    "OH": list(range(430, 460)),
    "OK": list(range(730, 750)),
    "OR": list(range(970, 980)),
    "PA": list(range(150, 197)),
    "RI": list(range(28, 30)),
    "SC": list(range(290, 300)),
    "SD": list(range(570, 578)),
    "TN": list(range(370, 386)),
    "TX": list(range(750, 800)) + list(range(885, 889)),
    "UT": list(range(840, 848)),
    "VT": list(range(50, 60)),
    "VA": list(range(220, 247)),
    "WA": list(range(980, 995)),
    "WV": list(range(247, 270)),
    "WI": list(range(530, 550)),
    "WY": list(range(820, 832)),
}
for _st, _prefixes in _zip3_map.items():
    for _p in _prefixes:
        ZIP3_TO_STATE[str(_p).zfill(3)] = _st


def assign_zcta_to_state_by_zip(zcta_code):
    """Assign a ZCTA to a state using ZIP code prefix mapping."""
    if len(zcta_code) >= 3:
        prefix = zcta_code[:3]
        return ZIP3_TO_STATE.get(prefix)
    return None


def assign_zcta_to_state_by_bbox(lng, lat):
    """Fallback: assign a ZCTA to a state based on centroid location."""
    for state, (minx, miny, maxx, maxy) in STATE_BBOXES.items():
        if minx <= lng <= maxx and miny <= lat <= maxy:
            return state
    return None


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)

    print("=" * 60)
    print("Fallback: Download Cities + ZCTAs from Census Shapefiles")
    print("=" * 60)

    # Load population caches
    print("\n1. Loading population data...")
    city_pop, zcta_pop = asyncio.get_event_loop().run_until_complete(
        load_population_cache()
    ) if False else (
        json.load(open(CACHE_DIR / "city_pop.json")) if (CACHE_DIR / "city_pop.json").exists() else {},
        json.load(open(CACHE_DIR / "zcta_pop.json")) if (CACHE_DIR / "zcta_pop.json").exists() else {},
    )
    print(f"  City records: {len(city_pop)}, ZCTA records: {len(zcta_pop)}")

    # --- CITIES ---
    print("\n2. Processing Cities (Places)...")
    sf_places = download_and_extract_shapefile(PLACES_URL, "cb_2022_us_place_500k")
    all_places = shapefile_to_geojson(sf_places)
    print(f"  Total places: {len(all_places)}")

    # Group by state FIPS
    state_cities = {}
    for f in all_places:
        statefp = f["properties"].get("STATEFP", "")
        state = FIPS_TO_STATE.get(statefp)
        if state:
            if state not in state_cities:
                state_cities[state] = []
            geoid = f["properties"].get("GEOID", f"{statefp}{f['properties'].get('PLACEFP', '')}")
            feature = {
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    "NAME": f["properties"].get("NAME", ""),
                    "GEOID": geoid,
                    "STATE": statefp,
                    "ALAND": f["properties"].get("ALAND", 0),
                    "POPULATION": city_pop.get(geoid, 0),
                },
            }
            state_cities[state].append(feature)

    cities_total = 0
    for state in sorted(state_cities.keys()):
        features = state_cities[state]
        outfile = OUTPUT_DIR / f"{state}_cities.geojson"
        with open(outfile, "w") as fp:
            json.dump({"type": "FeatureCollection", "features": features}, fp)
        cities_total += len(features)
        with_pop = sum(1 for f in features if f["properties"].get("POPULATION", 0) > 0)
        print(f"  {state}: {len(features)} cities ({with_pop} with population)")

    print(f"  -> Total: {cities_total} cities across {len(state_cities)} states")

    # --- ZCTAs ---
    print("\n3. Processing ZCTAs...")
    sf_zctas = download_and_extract_shapefile(ZCTA_URL, "cb_2020_us_zcta520_500k")
    all_zctas = shapefile_to_geojson(sf_zctas)
    print(f"  Total ZCTAs: {len(all_zctas)}")

    # ZCTAs don't have state FIPS - assign by ZIP prefix first, bbox fallback
    state_zctas = {}
    unassigned = 0
    for f in all_zctas:
        zcta_raw = (f["properties"].get("ZCTA5CE20") or
                    f["properties"].get("GEOID20") or
                    f["properties"].get("ZCTA5CE10", ""))
        # Try ZIP prefix mapping first (most reliable)
        state = assign_zcta_to_state_by_zip(zcta_raw)
        if not state:
            # Fallback to bounding box
            lng, lat = centroid(f["geometry"])
            if lng is not None:
                state = assign_zcta_to_state_by_bbox(lng, lat)
        if not state:
            unassigned += 1
            continue
        if state not in state_zctas:
            state_zctas[state] = []

        zcta_code = (f["properties"].get("ZCTA5CE20") or
                     f["properties"].get("GEOID20") or
                     f["properties"].get("ZCTA5CE10", ""))
        feature = {
            "type": "Feature",
            "geometry": f["geometry"],
            "properties": {
                "NAME": zcta_code,
                "GEOID20": zcta_code,
                "ZCTA5CE20": zcta_code,
                "ALAND20": f["properties"].get("ALAND20", 0),
                "POPULATION": zcta_pop.get(zcta_code, 0),
            },
        }
        state_zctas[state].append(feature)

    if unassigned:
        print(f"  Note: {unassigned} ZCTAs could not be assigned to a state")

    zctas_total = 0
    for state in sorted(state_zctas.keys()):
        features = state_zctas[state]
        outfile = OUTPUT_DIR / f"{state}_zctas.geojson"
        with open(outfile, "w") as fp:
            json.dump({"type": "FeatureCollection", "features": features}, fp)
        zctas_total += len(features)
        with_pop = sum(1 for f in features if f["properties"].get("POPULATION", 0) > 0)
        print(f"  {state}: {len(features)} ZCTAs ({with_pop} with population)")

    print(f"  -> Total: {zctas_total} ZCTAs across {len(state_zctas)} states")

    print("\n" + "=" * 60)
    print("DONE")
    print(f"  Cities: {cities_total}")
    print(f"  ZCTAs: {zctas_total}")
    print("=" * 60)


if __name__ == "__main__":
    main()
