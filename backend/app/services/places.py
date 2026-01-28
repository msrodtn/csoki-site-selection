"""
Google Places API service for trade area analysis.
Fetches nearby points of interest (POIs) within a radius of a location.
"""
import httpx
from typing import Optional
from pydantic import BaseModel
from app.core.config import settings


# POI Category mapping to Google Places types
POI_CATEGORIES = {
    "anchors": [
        "department_store",
        "shopping_mall",
        "supermarket",
        "grocery_or_supermarket",
        "home_goods_store",
        "furniture_store",
        "electronics_store",
    ],
    "quick_service": [
        "cafe",
        "bakery",
        "convenience_store",
        "gas_station",
        "pharmacy",
        "bank",
        "atm",
    ],
    "restaurants": [
        "restaurant",
        "meal_delivery",
        "meal_takeaway",
        "bar",
        "food",
    ],
    "retail": [
        "clothing_store",
        "shoe_store",
        "jewelry_store",
        "beauty_salon",
        "hair_care",
        "pet_store",
        "florist",
        "book_store",
        "sporting_goods_store",
    ],
}

# Reverse mapping for categorization
TYPE_TO_CATEGORY = {}
for category, types in POI_CATEGORIES.items():
    for t in types:
        TYPE_TO_CATEGORY[t] = category


class POI(BaseModel):
    """Point of Interest model."""
    place_id: str
    name: str
    category: str
    types: list[str]
    latitude: float
    longitude: float
    address: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None


class TradeAreaAnalysis(BaseModel):
    """Trade area analysis result."""
    center_latitude: float
    center_longitude: float
    radius_meters: int
    pois: list[POI]
    summary: dict[str, int]  # Count by category


async def fetch_nearby_pois(
    latitude: float,
    longitude: float,
    radius_meters: int = 1609,  # Default 1 mile
    api_key: Optional[str] = None,
) -> TradeAreaAnalysis:
    """
    Fetch nearby POIs using Google Places Nearby Search API.

    Args:
        latitude: Center latitude
        longitude: Center longitude
        radius_meters: Search radius in meters (default 1609 = 1 mile)
        api_key: Google Places API key (uses config if not provided)

    Returns:
        TradeAreaAnalysis with categorized POIs
    """
    key = api_key or settings.GOOGLE_PLACES_API_KEY
    if not key:
        raise ValueError("Google Places API key not configured")

    base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

    all_pois: list[POI] = []
    seen_place_ids: set[str] = set()

    # Fetch POIs for each category's types
    async with httpx.AsyncClient(timeout=30.0) as client:
        for category, place_types in POI_CATEGORIES.items():
            for place_type in place_types:
                params = {
                    "location": f"{latitude},{longitude}",
                    "radius": radius_meters,
                    "type": place_type,
                    "key": key,
                }

                try:
                    response = await client.get(base_url, params=params)
                    response.raise_for_status()
                    data = response.json()

                    if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                        continue

                    for place in data.get("results", []):
                        place_id = place.get("place_id")
                        if place_id in seen_place_ids:
                            continue
                        seen_place_ids.add(place_id)

                        # Determine category from types
                        place_types_list = place.get("types", [])
                        poi_category = category  # Default to search category
                        for pt in place_types_list:
                            if pt in TYPE_TO_CATEGORY:
                                poi_category = TYPE_TO_CATEGORY[pt]
                                break

                        geometry = place.get("geometry", {}).get("location", {})

                        poi = POI(
                            place_id=place_id,
                            name=place.get("name", "Unknown"),
                            category=poi_category,
                            types=place_types_list,
                            latitude=geometry.get("lat", 0),
                            longitude=geometry.get("lng", 0),
                            address=place.get("vicinity"),
                            rating=place.get("rating"),
                            user_ratings_total=place.get("user_ratings_total"),
                        )
                        all_pois.append(poi)

                except httpx.HTTPError:
                    # Continue on errors for individual type queries
                    continue

    # Calculate summary
    summary = {"anchors": 0, "quick_service": 0, "restaurants": 0, "retail": 0}
    for poi in all_pois:
        if poi.category in summary:
            summary[poi.category] += 1

    return TradeAreaAnalysis(
        center_latitude=latitude,
        center_longitude=longitude,
        radius_meters=radius_meters,
        pois=all_pois,
        summary=summary,
    )
