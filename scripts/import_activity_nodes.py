#!/usr/bin/env python3
"""
Import activity nodes from OpenStreetMap Overpass API into PostgreSQL.

Fetches shopping, entertainment, and dining POIs for target states (IA, NE, NV, ID)
and assigns traffic-gravity weights for heatmap visualization.

Usage:
    python scripts/import_activity_nodes.py
    python scripts/import_activity_nodes.py --states IA NE
    python scripts/import_activity_nodes.py --dry-run
"""

import argparse
import logging
import os
import sys
import time
from typing import Optional

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the backend directory to the path so we can import models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

TARGET_STATES = ["IA", "NE", "NV", "ID"]

# ISO 3166-2 codes for Overpass area lookups
STATE_ISO = {
    "IA": "US-IA",
    "NE": "US-NE",
    "NV": "US-NV",
    "ID": "US-ID",
}

# ============================================================================
# Weight classification system
# ============================================================================

# Brand-specific overrides (case-insensitive match on name or brand tag)
BRAND_WEIGHTS = {
    # Shopping — big box super (3.0)
    "walmart": ("shopping", "big_box_super", 3.0),
    "walmart supercenter": ("shopping", "big_box_super", 3.0),
    "walmart neighborhood market": ("shopping", "big_box_standard", 2.5),
    "target": ("shopping", "big_box_super", 3.0),
    "costco": ("shopping", "big_box_super", 3.0),
    "costco wholesale": ("shopping", "big_box_super", 3.0),
    "sam's club": ("shopping", "big_box_standard", 2.5),
    # Shopping — big box standard (2.5)
    "home depot": ("shopping", "big_box_standard", 2.5),
    "the home depot": ("shopping", "big_box_standard", 2.5),
    "lowe's": ("shopping", "big_box_standard", 2.5),
    "lowes": ("shopping", "big_box_standard", 2.5),
    "menards": ("shopping", "big_box_standard", 2.5),
    # Shopping — department store (2.0)
    "kohl's": ("shopping", "department_store", 2.0),
    "kohls": ("shopping", "department_store", 2.0),
    "jcpenney": ("shopping", "department_store", 2.0),
    "macy's": ("shopping", "department_store", 2.0),
    "nordstrom": ("shopping", "department_store", 2.0),
    "marshalls": ("shopping", "department_store", 2.0),
    "tj maxx": ("shopping", "department_store", 2.0),
    "ross": ("shopping", "department_store", 2.0),
    "burlington": ("shopping", "department_store", 2.0),
    # Shopping — electronics (2.0)
    "best buy": ("shopping", "electronics", 2.0),
    # Shopping — supermarket (1.8)
    "hy-vee": ("shopping", "supermarket", 1.8),
    "hyvee": ("shopping", "supermarket", 1.8),
    "fareway": ("shopping", "supermarket", 1.8),
    "kroger": ("shopping", "supermarket", 1.8),
    "albertsons": ("shopping", "supermarket", 1.8),
    "safeway": ("shopping", "supermarket", 1.8),
    "aldi": ("shopping", "supermarket", 1.8),
    "trader joe's": ("shopping", "supermarket", 1.8),
    "winco": ("shopping", "supermarket", 1.8),
    "smith's": ("shopping", "supermarket", 1.8),
    "food lion": ("shopping", "supermarket", 1.8),
    # Entertainment — major venues (2.5)
    "scheels": ("entertainment", "stadium_arena", 2.5),
    # Entertainment — movie theaters (2.0)
    "amc": ("entertainment", "movie_theater", 2.0),
    "amc theatres": ("entertainment", "movie_theater", 2.0),
    "regal": ("entertainment", "movie_theater", 2.0),
    "regal cinemas": ("entertainment", "movie_theater", 2.0),
    "marcus theatres": ("entertainment", "movie_theater", 2.0),
    "cinemark": ("entertainment", "movie_theater", 2.0),
    # Entertainment — fitness (1.5)
    "planet fitness": ("entertainment", "fitness_center", 1.5),
    "anytime fitness": ("entertainment", "fitness_center", 1.5),
    "orangetheory": ("entertainment", "fitness_center", 1.5),
    "ymca": ("entertainment", "fitness_center", 1.5),
    # Dining — QSR major (1.5)
    "mcdonald's": ("dining", "qsr_major", 1.5),
    "mcdonalds": ("dining", "qsr_major", 1.5),
    "chick-fil-a": ("dining", "qsr_major", 1.5),
    "starbucks": ("dining", "qsr_major", 1.5),
    "chipotle": ("dining", "qsr_major", 1.5),
    "chili's": ("dining", "sit_down_chain", 1.3),
    "applebee's": ("dining", "sit_down_chain", 1.3),
    "olive garden": ("dining", "sit_down_chain", 1.3),
    "buffalo wild wings": ("dining", "sit_down_chain", 1.3),
    "texas roadhouse": ("dining", "sit_down_chain", 1.3),
    "red robin": ("dining", "sit_down_chain", 1.3),
    "cracker barrel": ("dining", "sit_down_chain", 1.3),
    # Dining — QSR standard (1.2)
    "subway": ("dining", "qsr_standard", 1.2),
    "taco bell": ("dining", "qsr_standard", 1.2),
    "wendy's": ("dining", "qsr_standard", 1.2),
    "wendys": ("dining", "qsr_standard", 1.2),
    "burger king": ("dining", "qsr_standard", 1.2),
    "arby's": ("dining", "qsr_standard", 1.2),
    "popeyes": ("dining", "qsr_standard", 1.2),
    "sonic": ("dining", "qsr_standard", 1.2),
    "dairy queen": ("dining", "qsr_standard", 1.2),
    "jimmy john's": ("dining", "qsr_standard", 1.2),
    "panera": ("dining", "qsr_standard", 1.2),
    "panera bread": ("dining", "qsr_standard", 1.2),
    "dunkin'": ("dining", "qsr_standard", 1.2),
    "dunkin donuts": ("dining", "qsr_standard", 1.2),
    "panda express": ("dining", "qsr_standard", 1.2),
    "domino's": ("dining", "qsr_standard", 1.2),
    "pizza hut": ("dining", "qsr_standard", 1.2),
    "papa john's": ("dining", "qsr_standard", 1.2),
    "kfc": ("dining", "qsr_standard", 1.2),
    "five guys": ("dining", "qsr_standard", 1.2),
    "whataburger": ("dining", "qsr_standard", 1.2),
    "raising cane's": ("dining", "qsr_major", 1.5),
    "in-n-out": ("dining", "qsr_major", 1.5),
}

# OSM tag-based classification (tag_key, tag_value) -> (category, subcategory, weight)
TAG_WEIGHTS = {
    # Shopping
    ("shop", "supermarket"): ("shopping", "supermarket", 1.8),
    ("shop", "department_store"): ("shopping", "department_store", 2.0),
    ("shop", "mall"): ("shopping", "shopping_mall", 2.5),
    ("shop", "wholesale"): ("shopping", "big_box_standard", 2.5),
    ("shop", "electronics"): ("shopping", "electronics", 2.0),
    ("shop", "furniture"): ("shopping", "general_retail", 1.0),
    ("shop", "hardware"): ("shopping", "general_retail", 1.0),
    ("shop", "variety_store"): ("shopping", "general_retail", 1.0),
    ("shop", "general"): ("shopping", "general_retail", 1.0),
    # Entertainment
    ("amenity", "cinema"): ("entertainment", "movie_theater", 2.0),
    ("leisure", "fitness_centre"): ("entertainment", "fitness_center", 1.5),
    ("leisure", "bowling_alley"): ("entertainment", "bowling_alley", 1.2),
    ("leisure", "stadium"): ("entertainment", "stadium_arena", 2.5),
    ("leisure", "sports_centre"): ("entertainment", "fitness_center", 1.5),
    ("tourism", "theme_park"): ("entertainment", "amusement_park", 2.5),
    ("leisure", "water_park"): ("entertainment", "amusement_park", 2.5),
    ("tourism", "museum"): ("entertainment", "general_entertainment", 1.0),
    ("amenity", "theatre"): ("entertainment", "general_entertainment", 1.0),
    ("leisure", "amusement_arcade"): ("entertainment", "general_entertainment", 1.0),
    ("leisure", "miniature_golf"): ("entertainment", "general_entertainment", 1.0),
    # Dining
    ("amenity", "fast_food"): ("dining", "qsr_standard", 1.2),
    ("amenity", "restaurant"): ("dining", "sit_down_independent", 0.8),
    ("amenity", "bar"): ("dining", "bar_brewery", 1.0),
    ("amenity", "pub"): ("dining", "bar_brewery", 1.0),
    ("amenity", "cafe"): ("dining", "cafe_coffee", 0.8),
    ("amenity", "food_court"): ("dining", "food_court", 1.5),
    ("amenity", "ice_cream"): ("dining", "cafe_coffee", 0.8),
    ("craft", "brewery"): ("dining", "bar_brewery", 1.0),
}


def build_overpass_queries(state_iso: str) -> list[tuple[str, str]]:
    """Build per-category Overpass QL queries for a single state.

    Splitting by category avoids 504 timeouts on larger states.
    Returns list of (category_label, query_string) tuples.
    """
    shopping = f"""
[out:json][timeout:120];
area["ISO3166-2"="{state_iso}"]->.a;
(
  nwr["shop"="supermarket"](area.a);
  nwr["shop"="department_store"](area.a);
  nwr["shop"="mall"](area.a);
  nwr["shop"="wholesale"](area.a);
  nwr["shop"="electronics"](area.a);
  nwr["shop"="furniture"](area.a);
  nwr["shop"="hardware"](area.a);
  nwr["shop"="variety_store"](area.a);
  nwr["shop"="general"](area.a);
);
out center;
"""
    entertainment = f"""
[out:json][timeout:120];
area["ISO3166-2"="{state_iso}"]->.a;
(
  nwr["amenity"="cinema"](area.a);
  nwr["leisure"="fitness_centre"](area.a);
  nwr["leisure"="bowling_alley"](area.a);
  nwr["leisure"="stadium"](area.a);
  nwr["leisure"="sports_centre"](area.a);
  nwr["tourism"="theme_park"](area.a);
  nwr["leisure"="water_park"](area.a);
  nwr["tourism"="museum"](area.a);
  nwr["amenity"="theatre"](area.a);
  nwr["leisure"="amusement_arcade"](area.a);
  nwr["leisure"="miniature_golf"](area.a);
);
out center;
"""
    dining = f"""
[out:json][timeout:120];
area["ISO3166-2"="{state_iso}"]->.a;
(
  nwr["amenity"="fast_food"](area.a);
  nwr["amenity"="restaurant"](area.a);
  nwr["amenity"="bar"](area.a);
  nwr["amenity"="pub"](area.a);
  nwr["amenity"="cafe"](area.a);
  nwr["amenity"="food_court"](area.a);
  nwr["amenity"="ice_cream"](area.a);
  nwr["craft"="brewery"](area.a);
);
out center;
"""
    return [("shopping", shopping), ("entertainment", entertainment), ("dining", dining)]


def classify_element(element: dict) -> Optional[dict]:
    """Classify an OSM element into node_category, node_subcategory, and weight."""
    tags = element.get("tags", {})
    name = tags.get("name", "")
    brand = tags.get("brand", "")
    name_lower = name.lower().strip()
    brand_lower = brand.lower().strip()

    # Get coordinates — nodes have lat/lon directly, ways/relations use center
    if element["type"] == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        center = element.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        return None

    # Try brand-specific match first (higher priority)
    for key in [brand_lower, name_lower]:
        if key and key in BRAND_WEIGHTS:
            cat, subcat, weight = BRAND_WEIGHTS[key]
            return {
                "osm_id": element["id"],
                "name": name or brand or "Unknown",
                "node_category": cat,
                "node_subcategory": subcat,
                "weight": weight,
                "latitude": lat,
                "longitude": lon,
                "brand": brand or None,
            }

    # Try partial brand matching for common chains
    for brand_key, (cat, subcat, weight) in BRAND_WEIGHTS.items():
        if brand_lower and brand_key in brand_lower:
            return {
                "osm_id": element["id"],
                "name": name or brand or "Unknown",
                "node_category": cat,
                "node_subcategory": subcat,
                "weight": weight,
                "latitude": lat,
                "longitude": lon,
                "brand": brand or None,
            }

    # Fall back to tag-based classification
    for (tag_key, tag_value), (cat, subcat, weight) in TAG_WEIGHTS.items():
        if tags.get(tag_key) == tag_value:
            return {
                "osm_id": element["id"],
                "name": name or f"Unknown {tag_value}",
                "node_category": cat,
                "node_subcategory": subcat,
                "weight": weight,
                "latitude": lat,
                "longitude": lon,
                "brand": brand or None,
            }

    return None


def fetch_state_pois(state: str) -> list[dict]:
    """Fetch and classify all activity-node POIs for a state from Overpass.

    Splits into per-category queries to avoid 504 timeouts on larger states.
    """
    iso = STATE_ISO.get(state)
    if not iso:
        logger.error(f"Unknown state: {state}")
        return []

    queries = build_overpass_queries(iso)
    nodes = []
    seen_osm_ids = set()

    for cat_label, query in queries:
        logger.info(f"  {state}/{cat_label}: querying Overpass...")
        try:
            resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=200)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"  {state}/{cat_label}: Overpass request failed: {e}")
            continue

        elements = data.get("elements", [])
        count_before = len(nodes)
        for el in elements:
            classified = classify_element(el)
            if classified and classified["osm_id"] not in seen_osm_ids:
                classified["state"] = state
                nodes.append(classified)
                seen_osm_ids.add(classified["osm_id"])
        added = len(nodes) - count_before
        logger.info(f"  {state}/{cat_label}: {len(elements)} raw elements -> {added} new nodes")

        # Small delay between category queries
        time.sleep(3)

    # Summary
    cats = {}
    for n in nodes:
        cats[n["node_category"]] = cats.get(n["node_category"], 0) + 1
    logger.info(f"  {state} total: {len(nodes)} classified nodes — {cats}")

    return nodes


def upsert_nodes(engine, nodes: list[dict], dry_run: bool = False):
    """Insert or update activity nodes in the database."""
    if dry_run:
        logger.info(f"[DRY RUN] Would upsert {len(nodes)} nodes")
        return

    # Create table if not exists
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS activity_nodes (
                id SERIAL PRIMARY KEY,
                osm_id BIGINT UNIQUE,
                name VARCHAR(255),
                node_category VARCHAR(20) NOT NULL,
                node_subcategory VARCHAR(50),
                weight REAL NOT NULL DEFAULT 1.0,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                state VARCHAR(2),
                brand VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_activity_nodes_location
            ON activity_nodes (latitude, longitude)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_activity_nodes_category
            ON activity_nodes (node_category)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_activity_nodes_state
            ON activity_nodes (state)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_activity_nodes_bounds
            ON activity_nodes (node_category, latitude, longitude)
        """))
        conn.commit()

    # Batch upsert
    batch_size = 500
    inserted = 0
    updated = 0

    with engine.connect() as conn:
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            for node in batch:
                result = conn.execute(text("""
                    INSERT INTO activity_nodes (osm_id, name, node_category, node_subcategory, weight, latitude, longitude, state, brand)
                    VALUES (:osm_id, :name, :node_category, :node_subcategory, :weight, :latitude, :longitude, :state, :brand)
                    ON CONFLICT (osm_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        node_category = EXCLUDED.node_category,
                        node_subcategory = EXCLUDED.node_subcategory,
                        weight = EXCLUDED.weight,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        state = EXCLUDED.state,
                        brand = EXCLUDED.brand
                    RETURNING (xmax = 0) AS is_insert
                """), node)
                row = result.fetchone()
                if row and row[0]:
                    inserted += 1
                else:
                    updated += 1
            conn.commit()
            logger.info(f"  Batch {i // batch_size + 1}: processed {len(batch)} nodes")

    logger.info(f"Database: {inserted} inserted, {updated} updated")


def main():
    parser = argparse.ArgumentParser(description="Import activity nodes from OpenStreetMap")
    parser.add_argument("--states", nargs="+", default=TARGET_STATES, help="States to import (default: IA NE NV ID)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and classify but don't write to DB")
    parser.add_argument("--database-url", default=None, help="PostgreSQL connection string (or set DATABASE_URL env)")
    args = parser.parse_args()

    db_url = args.database_url or os.environ.get("DATABASE_URL")
    if not db_url and not args.dry_run:
        logger.error("DATABASE_URL not set. Use --database-url or set DATABASE_URL environment variable.")
        sys.exit(1)

    all_nodes = []
    for state in args.states:
        nodes = fetch_state_pois(state)
        all_nodes.extend(nodes)
        # Be polite to Overpass — wait between state queries
        if state != args.states[-1]:
            logger.info("  Waiting 10s between state queries (Overpass rate limit)...")
            time.sleep(10)

    logger.info(f"\nTotal: {len(all_nodes)} activity nodes across {len(args.states)} states")

    # Summary by category
    summary = {}
    for n in all_nodes:
        key = (n["node_category"], n["node_subcategory"])
        summary[key] = summary.get(key, 0) + 1
    logger.info("\nBreakdown by category/subcategory:")
    for (cat, subcat), count in sorted(summary.items()):
        logger.info(f"  {cat:15s} / {subcat:25s} : {count:5d}")

    if args.dry_run:
        logger.info("\n[DRY RUN] No database changes made.")
        return

    engine = create_engine(db_url)
    upsert_nodes(engine, all_nodes, dry_run=args.dry_run)
    logger.info("\nImport complete!")


if __name__ == "__main__":
    main()
