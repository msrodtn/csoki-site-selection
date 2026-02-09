"""
Viewport-level cache for demographic and POI data.

Caches ArcGIS population data and Mapbox retail node data by coarse geohash
to avoid redundant API calls when users pan/zoom within the same area.

Follows the caching pattern established in mapbox_matrix.py.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory caches keyed by geohash
_demographic_cache: dict[str, dict] = {}
_retail_node_cache: dict[str, dict] = {}

DEMOGRAPHIC_CACHE_TTL = 86400  # 24 hours (population data changes slowly)
RETAIL_NODE_CACHE_TTL = 3600   # 1 hour (POI data changes occasionally)


def _make_geohash(lat: float, lng: float, precision: int = 2) -> str:
    """
    Create a coarse grid key for caching.

    Precision 2 rounds to 0.01 degrees (~0.7mi cells).
    Precision 1 rounds to 0.1 degrees (~7mi cells).
    """
    grid_lat = round(lat, precision)
    grid_lng = round(lng, precision)
    return f"{grid_lat}_{grid_lng}"


# --- Demographic Cache ---

def get_cached_demographics(lat: float, lng: float) -> Optional[dict]:
    """Get cached demographic data for a location, or None if not cached/expired."""
    key = _make_geohash(lat, lng, precision=1)
    if key in _demographic_cache:
        entry = _demographic_cache[key]
        if time.time() - entry["_cached_at"] < DEMOGRAPHIC_CACHE_TTL:
            logger.debug(f"Demographics cache hit for {key}")
            return entry
    return None


def cache_demographics(lat: float, lng: float, data: dict):
    """Cache demographic data for a location."""
    key = _make_geohash(lat, lng, precision=1)
    data["_cached_at"] = time.time()
    _demographic_cache[key] = data
    logger.debug(f"Cached demographics for {key}")


# --- Retail Node Cache ---

def get_cached_retail_nodes(lat: float, lng: float) -> Optional[list]:
    """Get cached retail node POIs for a location, or None if not cached/expired."""
    key = _make_geohash(lat, lng, precision=1)
    if key in _retail_node_cache:
        entry = _retail_node_cache[key]
        if time.time() - entry["_cached_at"] < RETAIL_NODE_CACHE_TTL:
            logger.debug(f"Retail node cache hit for {key}")
            return entry["nodes"]
    return None


def cache_retail_nodes(lat: float, lng: float, nodes: list):
    """Cache retail node POIs for a location."""
    key = _make_geohash(lat, lng, precision=1)
    _retail_node_cache[key] = {
        "_cached_at": time.time(),
        "nodes": nodes,
    }
    logger.debug(f"Cached {len(nodes)} retail nodes for {key}")


# --- Cache Management ---

def clear_viewport_caches():
    """Clear all viewport caches."""
    global _demographic_cache, _retail_node_cache
    _demographic_cache = {}
    _retail_node_cache = {}
    logger.info("Viewport caches cleared")


def get_cache_stats() -> dict:
    """Get cache statistics."""
    now = time.time()
    valid_demo = sum(
        1 for entry in _demographic_cache.values()
        if now - entry["_cached_at"] < DEMOGRAPHIC_CACHE_TTL
    )
    valid_retail = sum(
        1 for entry in _retail_node_cache.values()
        if now - entry["_cached_at"] < RETAIL_NODE_CACHE_TTL
    )
    return {
        "demographic_cache": {
            "total_entries": len(_demographic_cache),
            "valid_entries": valid_demo,
            "ttl_seconds": DEMOGRAPHIC_CACHE_TTL,
        },
        "retail_node_cache": {
            "total_entries": len(_retail_node_cache),
            "valid_entries": valid_retail,
            "ttl_seconds": RETAIL_NODE_CACHE_TTL,
        },
    }
