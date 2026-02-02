"""
Property Search Service

Uses AI-powered web search to find commercial real estate listings
from multiple sources (Crexi, LoopNet, Zillow Commercial, etc.)
"""

import json
import re
from typing import Optional
from pydantic import BaseModel
from openai import AsyncOpenAI
import httpx

from ..core.config import settings


# Property types for filtering
PROPERTY_TYPES = {
    "retail": ["retail", "storefront", "shopping center", "strip mall"],
    "land": ["land", "lot", "vacant land", "development site"],
    "office": ["office", "office building", "office space"],
    "industrial": ["industrial", "warehouse", "distribution"],
    "mixed_use": ["mixed use", "mixed-use"],
}


class PropertyListing(BaseModel):
    """A commercial property listing from search results."""
    id: str
    address: str
    city: str
    state: str
    price: Optional[str] = None
    price_numeric: Optional[float] = None
    sqft: Optional[str] = None
    sqft_numeric: Optional[float] = None
    property_type: str
    source: str  # crexi, loopnet, zillow, etc.
    url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    listing_date: Optional[str] = None


class PropertySearchResult(BaseModel):
    """Result of a property search."""
    center_latitude: float
    center_longitude: float
    radius_miles: float
    search_query: str
    listings: list[PropertyListing]
    sources_searched: list[str]
    total_found: int


async def search_properties(
    latitude: float,
    longitude: float,
    radius_miles: float = 5.0,
    property_types: Optional[list[str]] = None,
) -> PropertySearchResult:
    """
    Search for commercial properties for sale near a location.

    Uses web search to find listings from multiple CRE platforms,
    then uses AI to extract structured property data.

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        radius_miles: Search radius in miles
        property_types: Filter by type (retail, land, office, industrial, mixed_use)

    Returns:
        PropertySearchResult with found listings
    """
    if not settings.TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY not configured")

    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")

    # Get location name for search query
    location_name = await reverse_geocode_to_city(latitude, longitude)

    # Build search queries for each source
    type_filter = ""
    if property_types:
        type_filter = " OR ".join(property_types)

    sources_to_search = ["Crexi", "LoopNet", "General"]
    all_listings: list[PropertyListing] = []

    print(f"[PropertySearch] Starting search for {location_name} (radius: {radius_miles} mi)")

    # Search each source
    for source in sources_to_search:
        try:
            listings = await search_source(
                source=source,
                location=location_name,
                radius_miles=radius_miles,
                property_types=property_types,
            )
            all_listings.extend(listings)
        except Exception as e:
            print(f"[PropertySearch] Error searching {source}: {e}")
            continue

    print(f"[PropertySearch] Total listings before geocoding: {len(all_listings)}")

    # Geocode listings that don't have coordinates
    all_listings = await geocode_listings(all_listings)

    # Filter to listings within radius
    filtered_listings = filter_by_radius(
        listings=all_listings,
        center_lat=latitude,
        center_lng=longitude,
        radius_miles=radius_miles,
    )

    # Deduplicate by address
    unique_listings = deduplicate_listings(filtered_listings)

    return PropertySearchResult(
        center_latitude=latitude,
        center_longitude=longitude,
        radius_miles=radius_miles,
        search_query=f"Commercial property for sale near {location_name}",
        listings=unique_listings,
        sources_searched=sources_to_search,
        total_found=len(unique_listings),
    )


async def reverse_geocode_to_city(lat: float, lng: float) -> str:
    """Get city/area name from coordinates using Google Geocoding API."""
    if not settings.GOOGLE_PLACES_API_KEY:
        # Fallback to coordinates-based search
        return f"{lat:.4f}, {lng:.4f}"

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
                # Extract city and state
                city = ""
                state = ""
                for component in result.get("address_components", []):
                    if "locality" in component["types"]:
                        city = component["long_name"]
                    if "administrative_area_level_1" in component["types"]:
                        state = component["short_name"]

                if city and state:
                    return f"{city}, {state}"
                elif city:
                    return city

    return f"{lat:.4f}, {lng:.4f}"


async def search_source(
    source: str,
    location: str,
    radius_miles: float,
    property_types: Optional[list[str]] = None,
) -> list[PropertyListing]:
    """Search a specific source for property listings using Tavily."""

    # Build more specific search queries that find actual listings
    type_terms = "retail OR office OR land OR industrial" if not property_types else " OR ".join(property_types)

    # Different query strategies for different sources
    if source.lower() == "crexi":
        query = f'"{location}" commercial property for sale price sqft crexi.com'
    elif source.lower() == "loopnet":
        query = f'"{location}" commercial real estate for sale loopnet.com listing'
    elif source.lower() == "general":
        # Broader search across all commercial real estate sites
        query = f'"{location}" commercial property for sale listing price address'
    else:
        query = f'"{location}" commercial property for sale {type_terms}'

    print(f"[PropertySearch] Searching {source} with query: {query}")

    # Use Tavily for web search
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "include_raw_content": True,
                "max_results": 10,
            },
        )

        if response.status_code != 200:
            print(f"[PropertySearch] Tavily search failed for {source}: {response.status_code} - {response.text}")
            return []

        data = response.json()
        results = data.get("results", [])

        print(f"[PropertySearch] {source} returned {len(results)} results")
        for i, r in enumerate(results[:3]):
            print(f"  [{i}] {r.get('title', 'No title')[:60]}...")

        if not results:
            return []

        # Use AI to extract structured property data
        listings = await extract_listings_with_ai(
            search_results=results,
            source=source,
            location=location,
        )

        print(f"[PropertySearch] Extracted {len(listings)} listings from {source}")

        return listings


async def extract_listings_with_ai(
    search_results: list[dict],
    source: str,
    location: str,
) -> list[PropertyListing]:
    """Use OpenAI to extract structured property data from search results."""

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Prepare content for AI extraction
    content_text = ""
    for i, result in enumerate(search_results):
        content_text += f"\n--- Result {i+1} ---\n"
        content_text += f"Title: {result.get('title', '')}\n"
        content_text += f"URL: {result.get('url', '')}\n"
        content_text += f"Content: {result.get('content', '')[:1500]}\n"
        if result.get('raw_content'):
            content_text += f"Raw Content: {result.get('raw_content', '')[:2000]}\n"

    prompt = f"""Extract commercial property listings from these search results for {location}.

Look for ANY property that appears to be for sale, including:
- Retail spaces, storefronts, shopping centers
- Office buildings, office space
- Land, lots, development sites
- Industrial, warehouse, distribution centers
- Mixed-use properties

For each property found, extract what you can find:
- address: street address (required - skip if not found)
- city: city name
- state: 2-letter state code
- price: price as shown (e.g., "$500,000", "$15/sqft", "Contact for pricing")
- price_numeric: just the number, null if unavailable
- sqft: square footage as shown
- sqft_numeric: just the number, null if unavailable
- property_type: one of: retail, land, office, industrial, mixed_use
- url: the listing URL
- description: brief description (max 100 chars)

Be generous in extraction - if you see something that looks like a property listing with an address and price, include it.

Return JSON: {{"listings": [...]}}
If no listings found, return: {{"listings": []}}

Search Results:
{content_text}
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a data extraction assistant. Extract structured property listing data from web search results. Return only valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # Handle both {"listings": [...]} and direct array formats
        listings_data = data.get("listings", data) if isinstance(data, dict) else data

        if not isinstance(listings_data, list):
            return []

        listings = []
        for i, item in enumerate(listings_data):
            if not item.get("address"):
                continue

            listing = PropertyListing(
                id=f"{source.lower()}_{i}_{hash(item.get('address', '')) % 10000}",
                address=item.get("address", ""),
                city=item.get("city", ""),
                state=item.get("state", ""),
                price=item.get("price"),
                price_numeric=item.get("price_numeric"),
                sqft=item.get("sqft"),
                sqft_numeric=item.get("sqft_numeric"),
                property_type=item.get("property_type", "retail"),
                source=source.lower(),
                url=item.get("url"),
                description=item.get("description"),
            )
            listings.append(listing)

        return listings

    except Exception as e:
        print(f"AI extraction error: {e}")
        return []


async def geocode_listings(listings: list[PropertyListing]) -> list[PropertyListing]:
    """Add coordinates to listings that don't have them."""
    if not settings.GOOGLE_PLACES_API_KEY:
        return listings

    async with httpx.AsyncClient(timeout=10.0) as client:
        for listing in listings:
            if listing.latitude and listing.longitude:
                continue

            # Build address for geocoding
            address_parts = [listing.address]
            if listing.city:
                address_parts.append(listing.city)
            if listing.state:
                address_parts.append(listing.state)

            full_address = ", ".join(address_parts)

            try:
                response = await client.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={
                        "address": full_address,
                        "key": settings.GOOGLE_PLACES_API_KEY,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("results"):
                        location = data["results"][0]["geometry"]["location"]
                        listing.latitude = location["lat"]
                        listing.longitude = location["lng"]
            except Exception as e:
                print(f"Geocoding error for {full_address}: {e}")
                continue

    return listings


def filter_by_radius(
    listings: list[PropertyListing],
    center_lat: float,
    center_lng: float,
    radius_miles: float,
) -> list[PropertyListing]:
    """Filter listings to those within the specified radius."""
    from math import radians, sin, cos, sqrt, atan2

    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in miles between two points."""
        R = 3959  # Earth's radius in miles

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    filtered = []
    for listing in listings:
        if not listing.latitude or not listing.longitude:
            continue

        distance = haversine_distance(
            center_lat, center_lng,
            listing.latitude, listing.longitude
        )

        if distance <= radius_miles:
            filtered.append(listing)

    return filtered


def deduplicate_listings(listings: list[PropertyListing]) -> list[PropertyListing]:
    """Remove duplicate listings based on address similarity."""
    seen_addresses: set[str] = set()
    unique: list[PropertyListing] = []

    for listing in listings:
        # Normalize address for comparison
        normalized = listing.address.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)

        if normalized not in seen_addresses:
            seen_addresses.add(normalized)
            unique.append(listing)

    return unique


async def check_api_keys() -> dict:
    """Check which API keys are configured for property search."""
    return {
        "tavily_configured": settings.TAVILY_API_KEY is not None,
        "openai_configured": settings.OPENAI_API_KEY is not None,
        "google_configured": settings.GOOGLE_PLACES_API_KEY is not None,
        "crexi_configured": settings.CREXI_API_KEY is not None,
        "all_required_configured": all([
            settings.TAVILY_API_KEY,
            settings.OPENAI_API_KEY,
        ]),
    }
