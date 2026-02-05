"""
Mapbox Search Box API service for POI discovery.

Uses Mapbox Search Box API which provides 170M+ POIs globally.

Key features:
- Category-based search with proximity filtering
- 6 POI categories: anchors, quick_service, restaurants, retail, entertainment, services
- Session-based pricing (cost-effective)
"""
import httpx
import logging
import math
from typing import Optional
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


# Mapbox category mapping - uses Mapbox's POI category IDs
# See: https://docs.mapbox.com/api/search/search-box/#poi-categories
MAPBOX_CATEGORIES = {
    "anchors": [
        "department_store",
        "shopping_mall",
        "supermarket",
        "grocery",
        "furniture_store",
        "electronics_store",
        "home_improvement_store",
    ],
    "quick_service": [
        "cafe",
        "coffee_shop",
        "convenience_store",
        "gas_station",
        "pharmacy",
        "fast_food",
    ],
    "restaurants": [
        "restaurant",
        "bar",
        "food_court",
        "bakery",
        "pizza",
        "mexican_restaurant",
        "chinese_restaurant",
        "american_restaurant",
    ],
    "retail": [
        "clothing_store",
        "shoe_store",
        "jewelry_store",
        "beauty_salon",
        "pet_store",
        "florist",
        "bookstore",
        "sporting_goods_store",
        "mobile_phone_store",  # Important for cellular competitor analysis
    ],
    "entertainment": [
        "movie_theater",
        "theater",
        "bowling_alley",
        "gym",
        "fitness_center",
        "park",
        "museum",
        "art_gallery",
        "amusement_park",
        "stadium",
    ],
    "services": [
        "bank",
        "credit_union",
        "insurance_agency",
        "doctor",
        "dentist",
        "hospital",
        "urgent_care",
        "veterinarian",
        "post_office",
        "laundry",
    ],
}

# Reverse mapping for categorization
CATEGORY_LOOKUP = {}
for category, types in MAPBOX_CATEGORIES.items():
    for t in types:
        CATEGORY_LOOKUP[t] = category


class MapboxPOI(BaseModel):
    """Point of Interest from Mapbox."""
    mapbox_id: str
    name: str
    category: str
    poi_category: Optional[str] = None
    latitude: float
    longitude: float
    address: Optional[str] = None
    full_address: Optional[str] = None


class MapboxTradeAreaAnalysis(BaseModel):
    """Trade area analysis result using Mapbox."""
    center_latitude: float
    center_longitude: float
    radius_meters: int
    pois: list[MapboxPOI]
    summary: dict[str, int]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the distance in meters between two points."""
    R = 6371000  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


async def fetch_mapbox_pois(
    latitude: float,
    longitude: float,
    radius_meters: int = 1609,  # Default 1 mile
    categories: Optional[list[str]] = None,
    limit_per_category: int = 25,
) -> MapboxTradeAreaAnalysis:
    """
    Fetch nearby POIs using Mapbox Search Box API.

    Uses the category search endpoint with proximity filtering.

    Args:
        latitude: Center latitude
        longitude: Center longitude
        radius_meters: Search radius in meters (default 1609 = 1 mile)
        categories: Optional list of categories to search (anchors, quick_service, etc.)
        limit_per_category: Maximum POIs per Mapbox category type

    Returns:
        MapboxTradeAreaAnalysis with categorized POIs
    """
    token = getattr(settings, 'MAPBOX_ACCESS_TOKEN', None)
    if not token:
        logger.error("Mapbox access token not configured")
        raise ValueError("Mapbox access token not configured. Set MAPBOX_ACCESS_TOKEN environment variable.")

    logger.info(f"Fetching Mapbox POIs for ({latitude}, {longitude}) within {radius_meters}m")

    # Determine which categories to search
    search_categories = categories or list(MAPBOX_CATEGORIES.keys())

    all_pois: list[MapboxPOI] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=60.0) as client:
        for our_category in search_categories:
            mapbox_types = MAPBOX_CATEGORIES.get(our_category, [])
            if not mapbox_types:
                continue

            # Search each Mapbox category type
            for mapbox_type in mapbox_types:
                try:
                    # Use Search Box API category endpoint
                    # Docs: https://docs.mapbox.com/api/search/search-box/#get-category-search
                    url = f"https://api.mapbox.com/search/searchbox/v1/category/{mapbox_type}"

                    params = {
                        "access_token": token,
                        "proximity": f"{longitude},{latitude}",
                        "limit": min(limit_per_category, 25),
                        "language": "en",
                    }

                    response = await client.get(url, params=params)

                    if response.status_code != 200:
                        # Log warning but continue - some categories may not exist
                        logger.debug(f"Mapbox category '{mapbox_type}' returned {response.status_code}")
                        continue

                    data = response.json()
                    features = data.get("features", [])

                    logger.debug(f"Category '{mapbox_type}': found {len(features)} features")

                    for feature in features:
                        props = feature.get("properties", {})
                        geom = feature.get("geometry", {})

                        mapbox_id = props.get("mapbox_id") or feature.get("id", "")
                        if not mapbox_id or mapbox_id in seen_ids:
                            continue

                        # Get coordinates
                        coords = geom.get("coordinates", [])
                        if len(coords) < 2:
                            continue

                        poi_lng, poi_lat = coords[0], coords[1]

                        # Filter by radius
                        distance = haversine_distance(latitude, longitude, poi_lat, poi_lng)
                        if distance > radius_meters:
                            continue

                        seen_ids.add(mapbox_id)

                        # Get POI category from Mapbox
                        poi_cat = None
                        poi_cats = props.get("poi_category", [])
                        if isinstance(poi_cats, list) and poi_cats:
                            poi_cat = poi_cats[0]
                        elif isinstance(poi_cats, str):
                            poi_cat = poi_cats

                        poi = MapboxPOI(
                            mapbox_id=mapbox_id,
                            name=props.get("name") or props.get("name_preferred") or "Unknown",
                            category=our_category,
                            poi_category=poi_cat or mapbox_type,
                            latitude=poi_lat,
                            longitude=poi_lng,
                            address=props.get("address"),
                            full_address=props.get("full_address"),
                        )
                        all_pois.append(poi)

                except httpx.HTTPError as e:
                    logger.warning(f"HTTP error for category '{mapbox_type}': {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Error fetching '{mapbox_type}': {e}")
                    continue

    # Calculate summary
    summary = {cat: 0 for cat in MAPBOX_CATEGORIES.keys()}
    for poi in all_pois:
        if poi.category in summary:
            summary[poi.category] += 1

    logger.info(f"Mapbox POI fetch complete: {len(all_pois)} total POIs, summary: {summary}")

    return MapboxTradeAreaAnalysis(
        center_latitude=latitude,
        center_longitude=longitude,
        radius_meters=radius_meters,
        pois=all_pois,
        summary=summary,
    )


async def check_mapbox_token() -> dict:
    """Check if Mapbox token is configured and valid."""
    token = getattr(settings, 'MAPBOX_ACCESS_TOKEN', None)

    if not token:
        return {
            "configured": False,
            "valid": False,
            "message": "MAPBOX_ACCESS_TOKEN not set in environment"
        }

    # Test token with a simple geocoding request
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.mapbox.com/search/geocode/v6/forward",
                params={
                    "q": "test",
                    "access_token": token,
                    "limit": 1,
                }
            )

            if response.status_code == 200:
                return {
                    "configured": True,
                    "valid": True,
                    "message": "Mapbox token is valid"
                }
            elif response.status_code == 401:
                return {
                    "configured": True,
                    "valid": False,
                    "message": "Mapbox token is invalid or expired"
                }
            else:
                return {
                    "configured": True,
                    "valid": False,
                    "message": f"Mapbox API returned status {response.status_code}"
                }

    except Exception as e:
        return {
            "configured": True,
            "valid": False,
            "message": f"Error testing Mapbox token: {str(e)}"
        }
