"""
Property Search Service - Link Out Strategy

Instead of scraping CRE platforms (which block us), we generate
pre-filled search URLs that users can open in external tabs.

This approach is:
- 100% reliable (no scraping failures)
- Always up-to-date (links to live search results)
- Zero maintenance (no bot detection to fight)
"""

from typing import Optional
from pydantic import BaseModel
import httpx

from ..core.config import settings


class ExternalSearchLink(BaseModel):
    """A link to an external CRE search platform."""
    name: str  # Display name (e.g., "Crexi", "LoopNet")
    url: str   # Pre-filled search URL
    icon: str  # Icon identifier for frontend


class PropertySearchLinks(BaseModel):
    """Collection of external search links for a location."""
    city: str
    state: str
    latitude: float
    longitude: float
    links: list[ExternalSearchLink]


def generate_crexi_url(city: str, state: str, property_type: Optional[str] = None) -> str:
    """
    Generate Crexi search URL for a location.

    Crexi URL format: https://www.crexi.com/properties?locations={city}-{state}
    Property types: retail, office, industrial, land, multifamily
    """
    city_slug = city.lower().replace(" ", "-")
    state_lower = state.lower()

    url = f"https://www.crexi.com/properties?locations={city_slug}-{state_lower}"

    # Add property type filter if specified
    if property_type:
        type_map = {
            "retail": "retail",
            "office": "office",
            "industrial": "industrial",
            "land": "land",
            "mixed_use": "mixed-use",
        }
        if property_type in type_map:
            url += f"&propertyTypes={type_map[property_type]}"

    return url


def generate_loopnet_url(city: str, state: str, property_type: Optional[str] = None) -> str:
    """
    Generate LoopNet search URL for a location.

    LoopNet URL format: https://www.loopnet.com/search/commercial-real-estate/{city}-{state}/for-sale/
    """
    city_slug = city.lower().replace(" ", "-")
    state_lower = state.lower()

    base_url = f"https://www.loopnet.com/search/commercial-real-estate/{city_slug}-{state_lower}/for-sale/"

    # Add property type filter if specified
    if property_type:
        type_map = {
            "retail": "1",  # LoopNet uses numeric IDs
            "office": "2",
            "industrial": "3",
            "land": "5",
            "mixed_use": "11",
        }
        if property_type in type_map:
            base_url += f"?sk=&e=false&pt={type_map[property_type]}"

    return base_url


def generate_commercialcafe_url(city: str, state: str) -> str:
    """
    Generate CommercialCafe search URL for a location.

    CommercialCafe is CoStar's free listing portal.
    """
    city_slug = city.lower().replace(" ", "-")
    state_lower = state.lower()

    return f"https://www.commercialcafe.com/commercial-real-estate/{state_lower}/{city_slug}/"


def generate_google_search_url(city: str, state: str) -> str:
    """
    Generate Google search URL for commercial real estate in the area.

    Useful as a fallback and for finding local broker listings.
    """
    query = f"commercial real estate for sale {city} {state}"
    return f"https://www.google.com/search?q={query.replace(' ', '+')}"


async def reverse_geocode_to_city(lat: float, lng: float) -> tuple[str, str]:
    """Get city and state from coordinates."""

    if not settings.GOOGLE_PLACES_API_KEY:
        return "", ""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "latlng": f"{lat},{lng}",
                    "key": settings.GOOGLE_PLACES_API_KEY,
                    "result_type": "locality|administrative_area_level_2",
                },
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    result = data["results"][0]
                    city = ""
                    state = ""
                    for component in result.get("address_components", []):
                        if "locality" in component["types"]:
                            city = component["long_name"]
                        if "administrative_area_level_1" in component["types"]:
                            state = component["short_name"]

                    return city, state
    except Exception as e:
        print(f"[Geocode] Error: {e}")

    return "", ""


async def get_property_search_links(
    latitude: float,
    longitude: float,
    property_type: Optional[str] = None,
) -> PropertySearchLinks:
    """
    Generate external search links for commercial properties near a location.

    Returns links to Crexi, LoopNet, and CommercialCafe with pre-filled searches.
    """
    # Get city/state from coordinates
    city, state = await reverse_geocode_to_city(latitude, longitude)

    if not city or not state:
        # Fallback to general search
        city = "commercial"
        state = "properties"

    print(f"[PropertySearch] Generating links for {city}, {state}")

    links = [
        ExternalSearchLink(
            name="Crexi",
            url=generate_crexi_url(city, state, property_type),
            icon="crexi",
        ),
        ExternalSearchLink(
            name="LoopNet",
            url=generate_loopnet_url(city, state, property_type),
            icon="loopnet",
        ),
        ExternalSearchLink(
            name="CommercialCafe",
            url=generate_commercialcafe_url(city, state),
            icon="commercialcafe",
        ),
        ExternalSearchLink(
            name="Google Search",
            url=generate_google_search_url(city, state),
            icon="google",
        ),
    ]

    return PropertySearchLinks(
        city=city,
        state=state,
        latitude=latitude,
        longitude=longitude,
        links=links,
    )


# Keep these for backwards compatibility with existing API
class MapBounds(BaseModel):
    """Map viewport bounds for geographic filtering."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


class PropertyListing(BaseModel):
    """A commercial property listing (kept for type compatibility)."""
    id: str
    address: str
    city: str
    state: str
    price: Optional[str] = None
    price_numeric: Optional[float] = None
    sqft: Optional[str] = None
    sqft_numeric: Optional[float] = None
    property_type: str
    source: str
    url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    listing_date: Optional[str] = None


class PropertySearchResult(BaseModel):
    """Result of a property search (kept for backwards compatibility)."""
    center_latitude: float
    center_longitude: float
    radius_miles: float
    search_query: str
    listings: list[PropertyListing]
    sources_searched: list[str]
    total_found: int
    bounds: Optional[MapBounds] = None
    # New field: external links for link-out strategy
    external_links: Optional[PropertySearchLinks] = None


async def search_properties(
    latitude: float,
    longitude: float,
    radius_miles: float = 5.0,
    property_types: Optional[list[str]] = None,
    bounds: Optional[MapBounds] = None,
) -> PropertySearchResult:
    """
    Search for commercial properties - now returns external links instead of scraped data.

    The scraping approach was unreliable due to bot protection. This new approach
    generates links to external CRE platforms that users can open in new tabs.
    """
    # Get location info
    city, state = await reverse_geocode_to_city(latitude, longitude)
    location_name = f"{city}, {state}" if city and state else f"{latitude:.4f}, {longitude:.4f}"

    print(f"[PropertySearch] Generating external links for {location_name}")

    # Generate external links
    property_type = property_types[0] if property_types else None
    external_links = await get_property_search_links(latitude, longitude, property_type)

    return PropertySearchResult(
        center_latitude=latitude,
        center_longitude=longitude,
        radius_miles=radius_miles,
        search_query=f"Commercial property for sale near {location_name}",
        listings=[],  # No scraped listings - use external links instead
        sources_searched=["Crexi", "LoopNet", "CommercialCafe"],
        total_found=0,  # External links, not scraped results
        bounds=bounds,
        external_links=external_links,
    )


async def check_api_keys() -> dict:
    """Check configured API keys."""
    return {
        "google_configured": settings.GOOGLE_PLACES_API_KEY is not None,
        # Only Google API needed for reverse geocoding
        "all_required_configured": settings.GOOGLE_PLACES_API_KEY is not None,
    }
