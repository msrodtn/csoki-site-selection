#!/usr/bin/env python3
"""
Merge per-state boundary files into national GeoJSON/NDJSON files.

Usage:
    python scripts/merge_national_boundaries.py

Input:
    mapbox-tilesets/states/{ST}_counties.geojson
    mapbox-tilesets/states/{ST}_cities.geojson
    mapbox-tilesets/states/{ST}_zctas.geojson
    mapbox-tilesets/states/{ST}_tracts.geojson
    mapbox-tilesets/counties.geojson           (existing 4-state IA/NE/NV/ID data)
    mapbox-tilesets/cities_with_pop.geojson     (existing 4-state data)
    mapbox-tilesets/zctas_with_pop.geojson      (existing 4-state data)

Output:
    mapbox-tilesets/national_counties.geojson
    mapbox-tilesets/national_cities.geojson
    mapbox-tilesets/national_zctas.geojson
    mapbox-tilesets/national_tracts.ndjson      (newline-delimited JSON)
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent / "mapbox-tilesets"
STATES_DIR = BASE_DIR / "states"

# States that were downloaded with download_national_boundaries.py
# (all 50 states + DC except Iowa which is in existing data)
DOWNLOADED_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

# Existing 4-state files include Iowa (19), Nebraska (31), Nevada (32), Idaho (16)
# The downloaded states also include NE, NV, ID so we need to handle overlap
EXISTING_ONLY_STATES = {"19"}  # Iowa FIPS - only in existing files, not downloaded


def load_geojson(filepath: Path) -> list:
    """Load features from a GeoJSON file."""
    if not filepath.exists():
        return []
    with open(filepath) as f:
        data = json.load(f)
    return data.get("features", [])


def validate_feature(feature: dict, required_props: list) -> bool:
    """Check that a feature has the required properties."""
    if not feature.get("geometry"):
        return False
    props = feature.get("properties", {})
    for prop in required_props:
        if prop not in props:
            return False
    return True


def normalize_county_from_existing(feature: dict) -> dict:
    """Normalize an existing 4-state county feature to match new schema."""
    props = feature["properties"]
    new_props = {
        "NAME": props.get("NAME", ""),
        "GEOID": props.get("GEOID", ""),
        "POPULATION": props.get("POPULATION", 0),
        "MEDIAN_INCOME": props.get("MEDIAN_INCOME", 0),
        "POP_DENSITY": props.get("POP_DENSITY", 0),
    }
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": new_props,
    }


def normalize_city_from_existing(feature: dict) -> dict:
    """Normalize an existing 4-state city feature to match new schema."""
    props = feature["properties"]
    new_props = {
        "NAME": props.get("NAME", ""),
        "GEOID": props.get("GEOID", ""),
        "STATE": props.get("STATEFP", props.get("STATE", "")),
        "ALAND": props.get("ALAND", 0),
        "POPULATION": props.get("POPULATION", 0),
    }
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": new_props,
    }


def normalize_zcta_from_existing(feature: dict) -> dict:
    """Normalize an existing 4-state ZCTA feature to match new schema."""
    props = feature["properties"]
    geoid20 = props.get("GEOID20") or props.get("ZCTA5CE20", "")
    new_props = {
        "NAME": props.get("NAME", props.get("ZCTA5CE20", "")),
        "GEOID20": geoid20,
        "ZCTA5CE20": props.get("ZCTA5CE20", geoid20),
        "ALAND20": props.get("ALAND20", 0),
        "POPULATION": props.get("POPULATION", 0),
    }
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": new_props,
    }


def merge_counties():
    """Merge all county files into national_counties.geojson."""
    print("COUNTIES")
    all_features = []
    seen_geoids = set()

    # Load existing 4-state data (for Iowa only, since NE/NV/ID are re-downloaded)
    existing_file = BASE_DIR / "counties.geojson"
    if existing_file.exists():
        existing = load_geojson(existing_file)
        iowa_count = 0
        for f in existing:
            props = f.get("properties", {})
            geoid = props.get("GEOID", "")
            statefp = props.get("STATEFP", "")
            # Only include Iowa from existing (NE/NV/ID will come from new downloads)
            if statefp in EXISTING_ONLY_STATES and geoid not in seen_geoids:
                all_features.append(normalize_county_from_existing(f))
                seen_geoids.add(geoid)
                iowa_count += 1
        print(f"  Iowa (existing): {iowa_count} counties")

    # Load per-state downloads
    for state in sorted(DOWNLOADED_STATES):
        filepath = STATES_DIR / f"{state}_counties.geojson"
        features = load_geojson(filepath)
        added = 0
        for f in features:
            geoid = f.get("properties", {}).get("GEOID", "")
            if geoid and geoid not in seen_geoids:
                if validate_feature(f, ["NAME", "GEOID", "POPULATION"]):
                    all_features.append(f)
                    seen_geoids.add(geoid)
                    added += 1
        if features:
            print(f"  {state}: {added} counties")

    output = {"type": "FeatureCollection", "features": all_features}
    out_path = BASE_DIR / "national_counties.geojson"
    with open(out_path, "w") as fp:
        json.dump(output, fp)
    print(f"  -> Total: {len(all_features)} counties -> {out_path.name}")
    return len(all_features)


def merge_cities():
    """Merge all city files into national_cities.geojson."""
    print("\nCITIES")
    all_features = []
    seen_geoids = set()

    # Load existing 4-state data (Iowa only)
    existing_file = BASE_DIR / "cities_with_pop.geojson"
    if existing_file.exists():
        existing = load_geojson(existing_file)
        iowa_count = 0
        for f in existing:
            props = f.get("properties", {})
            geoid = props.get("GEOID", "")
            statefp = props.get("STATEFP", "")
            if statefp in EXISTING_ONLY_STATES and geoid not in seen_geoids:
                all_features.append(normalize_city_from_existing(f))
                seen_geoids.add(geoid)
                iowa_count += 1
        print(f"  Iowa (existing): {iowa_count} cities")

    # Load per-state downloads
    for state in sorted(DOWNLOADED_STATES):
        filepath = STATES_DIR / f"{state}_cities.geojson"
        features = load_geojson(filepath)
        added = 0
        for f in features:
            geoid = f.get("properties", {}).get("GEOID", "")
            if geoid and geoid not in seen_geoids:
                if validate_feature(f, ["NAME", "GEOID"]):
                    all_features.append(f)
                    seen_geoids.add(geoid)
                    added += 1
        if features:
            print(f"  {state}: {added} cities")

    output = {"type": "FeatureCollection", "features": all_features}
    out_path = BASE_DIR / "national_cities.geojson"
    with open(out_path, "w") as fp:
        json.dump(output, fp)
    print(f"  -> Total: {len(all_features)} cities -> {out_path.name}")
    return len(all_features)


def merge_zctas():
    """Merge all ZCTA files into national_zctas.geojson, deduplicating by GEOID20."""
    print("\nZCTAs")
    all_features = []
    seen_geoids = set()

    # Load existing 4-state data (Iowa ZCTAs only)
    # Note: ZCTAs from existing file may overlap with downloaded states
    # since they use bounding boxes. We deduplicate by GEOID20.
    existing_file = BASE_DIR / "zctas_with_pop.geojson"
    if existing_file.exists():
        existing = load_geojson(existing_file)
        iowa_count = 0
        for f in existing:
            props = f.get("properties", {})
            geoid20 = props.get("GEOID20") or props.get("ZCTA5CE20", "")
            # We can't filter ZCTAs by state FIPS (they don't have one),
            # so include all from existing that aren't duplicated later
            if geoid20 and geoid20 not in seen_geoids:
                all_features.append(normalize_zcta_from_existing(f))
                seen_geoids.add(geoid20)
                iowa_count += 1
        print(f"  Existing (4-state): {iowa_count} ZCTAs")

    # Load per-state downloads
    for state in sorted(DOWNLOADED_STATES):
        filepath = STATES_DIR / f"{state}_zctas.geojson"
        features = load_geojson(filepath)
        added = 0
        dupes = 0
        for f in features:
            props = f.get("properties", {})
            geoid20 = props.get("GEOID20") or props.get("ZCTA5CE20", "")
            if geoid20 and geoid20 not in seen_geoids:
                all_features.append(f)
                seen_geoids.add(geoid20)
                added += 1
            elif geoid20:
                dupes += 1
        if features:
            msg = f"  {state}: {added} ZCTAs"
            if dupes:
                msg += f" ({dupes} duplicates skipped)"
            print(msg)

    output = {"type": "FeatureCollection", "features": all_features}
    out_path = BASE_DIR / "national_zctas.geojson"
    with open(out_path, "w") as fp:
        json.dump(output, fp)
    print(f"  -> Total: {len(all_features)} unique ZCTAs -> {out_path.name}")
    return len(all_features)


def merge_tracts():
    """Merge all tract files into national_tracts.ndjson (one feature per line)."""
    print("\nTRACTS (NDJSON)")
    total = 0
    seen_geoids = set()

    out_path = BASE_DIR / "national_tracts.ndjson"
    with open(out_path, "w") as fp:
        # No existing tract data for Iowa in old files, only from downloaded states
        # (and TN from tn_tracts.geojson)

        # Check for TN data from the earlier single-state download
        tn_file = BASE_DIR / "tn_tracts.geojson"
        if tn_file.exists():
            tn_features = load_geojson(tn_file)
            tn_count = 0
            for f in tn_features:
                geoid = f.get("properties", {}).get("GEOID", "")
                if geoid and geoid not in seen_geoids:
                    if validate_feature(f, ["NAME", "GEOID", "POPULATION"]):
                        fp.write(json.dumps(f) + "\n")
                        seen_geoids.add(geoid)
                        tn_count += 1
                        total += 1
            if tn_count:
                print(f"  TN (existing): {tn_count} tracts")

        # Load per-state downloads
        for state in sorted(DOWNLOADED_STATES):
            filepath = STATES_DIR / f"{state}_tracts.geojson"
            features = load_geojson(filepath)
            added = 0
            for f in features:
                geoid = f.get("properties", {}).get("GEOID", "")
                if geoid and geoid not in seen_geoids:
                    if validate_feature(f, ["NAME", "GEOID", "POPULATION"]):
                        fp.write(json.dumps(f) + "\n")
                        seen_geoids.add(geoid)
                        added += 1
                        total += 1
            if features:
                print(f"  {state}: {added} tracts")

    print(f"  -> Total: {total} tracts -> {out_path.name}")
    return total


def main():
    print("=" * 60)
    print("Merge National Boundary Data")
    print("=" * 60)

    # Check states directory exists
    if not STATES_DIR.exists():
        print(f"\nERROR: States directory not found: {STATES_DIR}")
        print("Run download_national_boundaries.py first.")
        return

    # Count available state files
    available = set()
    for f in STATES_DIR.glob("*_counties.geojson"):
        available.add(f.stem.split("_")[0])
    print(f"\nFound per-state data for {len(available)} states: {', '.join(sorted(available))}")

    missing = set(DOWNLOADED_STATES) - available
    if missing:
        print(f"WARNING: Missing states: {', '.join(sorted(missing))}")

    print()
    county_count = merge_counties()
    city_count = merge_cities()
    zcta_count = merge_zctas()
    tract_count = merge_tracts()

    print("\n" + "=" * 60)
    print("MERGE COMPLETE")
    print("=" * 60)
    print(f"  Counties:  {county_count:,}")
    print(f"  Cities:    {city_count:,}")
    print(f"  ZCTAs:     {zcta_count:,}")
    print(f"  Tracts:    {tract_count:,}")
    print(f"\n  Output directory: {BASE_DIR}")
    print(f"  Files:")
    print(f"    national_counties.geojson")
    print(f"    national_cities.geojson")
    print(f"    national_zctas.geojson")
    print(f"    national_tracts.ndjson")


if __name__ == "__main__":
    main()
