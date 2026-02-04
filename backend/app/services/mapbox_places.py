"""
Mapbox Search Box API service for POI discovery.

This is a proof-of-concept replacement for Google Places Nearby Search.
Uses Mapbox Search Box API which provides 170M+ POIs globally.

Key differences from Google Places:
- Single API call with category filters (vs 28 separate calls)
- Session-based pricing (more cost-effective)
- Different category taxonomy
"""
import httpx
from typing import Optional
from pydantic import BaseModel

from app.core.config import settings


# Mapbox category mapping to match our existing POI categories
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
        "bank",
        "atm",
    ],
    "restaurants": [
        "restaurant",
        "fast_food",
        "bar",
        "food_court",
        "bakery",
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


async def fetch_mapbox_pois(
    latitude: float,
    longitude: float,
    radius_meters: int = 1609,  # Default 1 mile
    categories: Optional[list[str]] = None,
    limit: int = 100,
) -> MapboxTradeAreaAnalysis:
    """
    Fetch nearby POIs using Mapbox Search Box API.

    This makes significantly fewer API calls than Google Places:
    - Google: 28 separate calls (one per POI type)
    - Mapbox: 1-4 calls (one per category group, or single call)

    Args:
        latitude: Center latitude
        longitude: Center longitude
        radius_meters: Search radius in meters (default 1609 = 1 mile)
        categories: Optional list of categories to search (anchors, quick_service, etc.)
        limit: Maximum POIs to return per category

    Returns:
        MapboxTradeAreaAnalysis with categorized POIs
    """
    # Use Mapbox token from settings
    token = getattr(settings, 'MAPBOX_ACCESS_TOKEN', None)
    if not token:
        raise ValueError("Mapbox access token not configured. Set MAPBOX_ACCESS_TOKEN environment variable.")

    # Determine which categories to search
    search_categories = categories or list(MAPBOX_CATEGORIES.keys())

    all_pois: list[MapboxPOI] = []
    seen_ids: set[str] = set()

    # Convert radius to bbox (approximate)
    # 1 degree latitude ~= 111km, longitude varies by latitude
    lat_delta = radius_meters / 111000
    lng_delta = radius_meters / (111000 * abs(cos_deg(latitude)))

    bbox = f"{longitude - lng_delta},{latitude - lat_delta},{longitude + lng_delta},{latitude + lat_delta}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        for our_category in search_categories:
            mapbox_types = MAPBOX_CATEGORIES.get(our_category, [])
            if not mapbox_types:
                continue

            # Build category filter for Mapbox
            # Mapbox uses comma-separated POI categories
            poi_category_filter = ",".join(mapbox_types)

            try:
                # Use Search Box API category endpoint
                # https://docs.mapbox.com/api/search/search-box/#category-search
                params = {
                    "access_token": token,
                    "bbox": bbox,
                    "limit": min(limit, 25),  # Mapbox limit per request
                    "language": "en",
                    "poi_category": poi_category_filter,
                }

                response = await client.get(
                    "https://api.mapbox.com/search/searchbox/v1/category/" + mapbox_types[0],
                    params=params,
                )

                if response.status_code != 200:
                    # Try alternative: forward geocoding with type filter
                    params = {
                        "q": our_category.replace("_", " "),
                        "access_token": token,
                        "proximity": f"{longitude},{latitude}",
                        "bbox": bbox,
                        "types": "poi",
                        "limit": min(limit, 10),
                        "language": "en",
                    }

                    response = await client.get(
                        "https://api.mapbox.com/search/geocode/v6/forward",
                        params=params,
                    )

                    if response.status_code != 200:
                        continue

                data = response.json()

                # Parse features from response
                features = data.get("features", [])

                for feature in features:
                    # Handle both Search Box and Geocoding API response formats
                    if "properties" in feature:
                        props = feature["properties"]
                        geom = feature.get("geometry", {})

                        mapbox_id = props.get("mapbox_id") or feature.get("id", "")

                        if mapbox_id in seen_ids:
                            continue
                        seen_ids.add(mapbox_id)

                        # Get coordinates
                        coords = geom.get("coordinates", [0, 0])
                        if len(coords) >= 2:
                            lng, lat = coords[0], coords[1]
                        else:
                            continue

                        # Get POI category from Mapbox
                        poi_cat = None
                        if "poi_category" in props:
                            poi_cats = props["poi_category"]
                            if isinstance(poi_cats, list) and poi_cats:
                                poi_cat = poi_cats[0]
                            elif isinstance(poi_cats, str):
                                poi_cat = poi_cats

                        poi = MapboxPOI(
                            mapbox_id=mapbox_id,
                            name=props.get("name", props.get("name_preferred", "Unknown")),
                            category=our_category,
                            poi_category=poi_cat,
                            latitude=lat,
                            longitude=lng,
                            address=props.get("address"),
                            full_address=props.get("full_address"),
                        )
                        all_pois.append(poi)

            except httpx.HTTPError as e:
                print(f"Mapbox API error for {our_category}: {e}")
                continue

    # Calculate summary
    summary = {cat: 0 for cat in MAPBOX_CATEGORIES.keys()}
    for poi in all_pois:
        if poi.category in summary:
            summary[poi.category] += 1

    return MapboxTradeAreaAnalysis(
        center_latitude=latitude,
        center_longitude=longitude,
        radius_meters=radius_meters,
        pois=all_pois,
        summary=summary,
    )


def cos_deg(degrees: float) -> float:
    """Calculate cosine of degrees."""
    import math
    return math.cos(math.radians(degrees))


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
