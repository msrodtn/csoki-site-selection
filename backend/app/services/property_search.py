"""
Property Search Service

Direct scraping approach:
1. Construct Crexi/LoopNet search URLs for the target location
2. Scrape their search result pages directly
3. Use AI to extract listing data from HTML
4. Geocode and filter results
"""

import asyncio
import json
import re
import urllib.parse
from typing import Optional
from pydantic import BaseModel
import anthropic
from bs4 import BeautifulSoup
import httpx

from ..core.config import settings


# Browser-like headers to avoid blocks
SCRAPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


# Property types for filtering
PROPERTY_TYPES = {
    "retail": ["retail", "storefront", "shopping center", "strip mall", "restaurant"],
    "land": ["land", "lot", "vacant land", "development site", "acreage"],
    "office": ["office", "office building", "office space", "professional"],
    "industrial": ["industrial", "warehouse", "distribution", "flex space", "manufacturing"],
    "mixed_use": ["mixed use", "mixed-use", "live/work"],
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


class MapBounds(BaseModel):
    """Map viewport bounds for geographic filtering."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


class PropertySearchResult(BaseModel):
    """Result of a property search."""
    center_latitude: float
    center_longitude: float
    radius_miles: float
    search_query: str
    listings: list[PropertyListing]
    sources_searched: list[str]
    total_found: int
    bounds: Optional[MapBounds] = None


async def search_properties(
    latitude: float,
    longitude: float,
    radius_miles: float = 5.0,
    property_types: Optional[list[str]] = None,
    bounds: Optional[MapBounds] = None,
) -> PropertySearchResult:
    """
    Search for commercial properties for sale near a location.

    Direct scraping approach:
    1. Construct Crexi/LoopNet search URLs
    2. Scrape their search result pages directly
    3. Use AI to extract listing data from HTML
    """
    # Get location name for search query
    location_name = await reverse_geocode_to_city(latitude, longitude)

    print(f"[PropertySearch] Starting direct scrape search for {location_name}")

    all_listings: list[PropertyListing] = []
    sources_searched: list[str] = []

    # Parse city and state from location name
    city, state = parse_location_parts(location_name)

    if not city:
        print(f"[PropertySearch] Could not parse city from: {location_name}")
        return PropertySearchResult(
            center_latitude=latitude,
            center_longitude=longitude,
            radius_miles=radius_miles,
            search_query=f"Commercial property for sale near {location_name}",
            listings=[],
            sources_searched=[],
            total_found=0,
            bounds=bounds,
        )

    # Run direct scraping in parallel for each source
    search_tasks = [
        scrape_crexi_search(city, state, property_types),
        scrape_loopnet_search(city, state, property_types),
    ]

    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    source_names = ["Crexi", "LoopNet"]
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[PropertySearch] Error scraping {source_names[i]}: {result}")
            continue
        sources_searched.append(source_names[i])
        if result:
            all_listings.extend(result)
        print(f"[PropertySearch] {source_names[i]}: Found {len(result) if result else 0} listings")

    print(f"[PropertySearch] Total listings before geocoding: {len(all_listings)}")

    # Geocode listings without coordinates
    all_listings = await geocode_listings(all_listings)

    print(f"[PropertySearch] Total listings after geocoding: {len(all_listings)}")

    # Filter by bounds or radius
    if bounds:
        filtered_listings = filter_by_bounds(
            all_listings, bounds.min_lat, bounds.max_lat, bounds.min_lng, bounds.max_lng
        )
        print(f"[PropertySearch] Listings within bounds: {len(filtered_listings)}")
    else:
        filtered_listings = filter_by_radius(
            all_listings, latitude, longitude, radius_miles
        )
        print(f"[PropertySearch] Listings within {radius_miles} miles: {len(filtered_listings)}")

    # Deduplicate
    unique_listings = deduplicate_listings(filtered_listings)

    print(f"[PropertySearch] Returning {len(unique_listings)} unique listings")

    return PropertySearchResult(
        center_latitude=latitude,
        center_longitude=longitude,
        radius_miles=radius_miles,
        search_query=f"Commercial property for sale near {location_name}",
        listings=unique_listings,
        sources_searched=sources_searched,
        total_found=len(unique_listings),
        bounds=bounds,
    )


def parse_location_parts(location_name: str) -> tuple[str, str]:
    """Parse 'City, ST' format into city and state."""
    parts = location_name.split(",")
    if len(parts) >= 2:
        city = parts[0].strip()
        state = parts[1].strip()
        return city, state
    return location_name.strip(), ""


async def scrape_crexi_search(
    city: str,
    state: str,
    property_types: Optional[list[str]] = None,
) -> list[PropertyListing]:
    """
    Directly scrape Crexi's search results page.

    Crexi URL format: https://www.crexi.com/properties?locations={city}-{state}
    """
    # Format city for URL (lowercase, hyphens for spaces)
    city_slug = city.lower().replace(" ", "-")
    state_lower = state.lower()

    search_url = f"https://www.crexi.com/properties?locations={city_slug}-{state_lower}"

    print(f"[Crexi] Scraping search page: {search_url}")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(search_url, headers=SCRAPE_HEADERS)

            if response.status_code != 200:
                print(f"[Crexi] Search page returned {response.status_code}")
                return []

            html = response.text
            print(f"[Crexi] Got {len(html)} bytes of HTML")

            # Check if blocked
            if "access denied" in html.lower() or "captcha" in html.lower():
                print("[Crexi] Access blocked (captcha or denied)")
                return []

            # Extract listings using AI
            listings = await extract_listings_from_html_with_ai(
                html, "Crexi", city, state, search_url, property_types
            )

            return listings

    except Exception as e:
        print(f"[Crexi] Scrape error: {e}")
        return []


async def scrape_loopnet_search(
    city: str,
    state: str,
    property_types: Optional[list[str]] = None,
) -> list[PropertyListing]:
    """
    Directly scrape LoopNet's search results page.

    LoopNet URL format: https://www.loopnet.com/search/commercial-real-estate/{city}-{state}/for-sale/
    """
    # Format city for URL (lowercase, hyphens for spaces)
    city_slug = city.lower().replace(" ", "-")
    state_lower = state.lower()

    search_url = f"https://www.loopnet.com/search/commercial-real-estate/{city_slug}-{state_lower}/for-sale/"

    print(f"[LoopNet] Scraping search page: {search_url}")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(search_url, headers=SCRAPE_HEADERS)

            if response.status_code != 200:
                print(f"[LoopNet] Search page returned {response.status_code}")
                return []

            html = response.text
            print(f"[LoopNet] Got {len(html)} bytes of HTML")

            # Check if blocked
            if "access denied" in html.lower() or "captcha" in html.lower() or "cloudflare" in html.lower():
                print("[LoopNet] Access blocked")
                return []

            # Extract listings using AI
            listings = await extract_listings_from_html_with_ai(
                html, "LoopNet", city, state, search_url, property_types
            )

            return listings

    except Exception as e:
        print(f"[LoopNet] Scrape error: {e}")
        return []


async def extract_listings_from_html_with_ai(
    html: str,
    source: str,
    city: str,
    state: str,
    search_url: str,
    property_types: Optional[list[str]] = None,
) -> list[PropertyListing]:
    """
    Use Claude AI to extract property listings from scraped HTML.

    This works because we're giving the AI the actual search results page HTML,
    not Tavily's snippets of category pages.
    """
    if not settings.ANTHROPIC_API_KEY:
        print(f"[{source}] No Anthropic API key, using BeautifulSoup fallback")
        return extract_listings_from_html_bs(html, source, city, state)

    # Parse HTML to extract just the listing-relevant parts
    soup = BeautifulSoup(html, 'html.parser')

    # Remove script, style, nav, footer elements
    for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
        tag.decompose()

    # Get text content, limited to reasonable size
    text_content = soup.get_text(separator="\n", strip=True)

    # Also look for structured data
    json_ld_data = []
    for script in BeautifulSoup(html, 'html.parser').find_all('script', type='application/ld+json'):
        try:
            if script.string:
                data = json.loads(script.string)
                json_ld_data.append(data)
        except:
            pass

    # Prepare content for AI - include text and any structured data
    ai_content = f"Page text content:\n{text_content[:15000]}"
    if json_ld_data:
        ai_content += f"\n\nStructured data (JSON-LD):\n{json.dumps(json_ld_data, indent=2)[:5000]}"

    prompt = f"""Extract commercial property listings from this {source} search results page for {city}, {state}.

The page HTML has been cleaned to show just the text content. Look for property cards/listings that contain:
- Street addresses (e.g., "123 Main St", "456 Oak Avenue")
- Prices (e.g., "$500,000", "$1.2M")
- Square footage (e.g., "2,500 SF", "10,000 sq ft")
- Property types (retail, office, land, industrial, warehouse)

For each distinct property listing found, extract:
- address: the street address (REQUIRED - skip entries without clear addresses)
- city: "{city}" (use this value)
- state: "{state}" (use this value)
- price: price as shown
- price_numeric: numeric price value (no commas/symbols), null if not available
- sqft: square footage as shown
- sqft_numeric: numeric sqft value, null if not available
- property_type: one of: retail, land, office, industrial, mixed_use
- description: brief description (max 100 chars)

Return ONLY valid JSON: {{"listings": [...]}}
If no property listings found, return: {{"listings": []}}

Page content:
{ai_content}
"""

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            system="Extract property listings from CRE search results. Return only valid JSON with real property addresses.",
        )

        content = response.content[0].text

        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        listings_data = data.get("listings", data) if isinstance(data, dict) else data

        if not isinstance(listings_data, list):
            print(f"[{source}] AI returned non-list: {type(listings_data)}")
            return []

        listings = []
        for i, item in enumerate(listings_data):
            if not item.get("address"):
                continue

            # Validate it looks like a real address
            addr = item.get("address", "")
            if not re.match(r'\d+\s+\w', addr):
                continue

            prop_type = item.get("property_type", "retail")
            if property_types and prop_type not in property_types:
                continue

            listing = PropertyListing(
                id=f"{source.lower()}_{i}_{hash(addr) % 10000}",
                address=addr,
                city=item.get("city", city),
                state=item.get("state", state),
                price=item.get("price"),
                price_numeric=item.get("price_numeric"),
                sqft=item.get("sqft"),
                sqft_numeric=item.get("sqft_numeric"),
                property_type=prop_type,
                source=source.lower(),
                url=search_url,
                description=item.get("description"),
            )
            listings.append(listing)

        print(f"[{source}] AI extracted {len(listings)} listings from HTML")
        return listings

    except Exception as e:
        print(f"[{source}] AI extraction error: {e}")
        return extract_listings_from_html_bs(html, source, city, state)


def extract_listings_from_html_bs(
    html: str,
    source: str,
    city: str,
    state: str,
) -> list[PropertyListing]:
    """
    Fallback: Extract listings using BeautifulSoup patterns.
    """
    listings = []
    seen = set()

    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()

    # Look for address patterns
    address_pattern = re.compile(
        r'(\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Za-z][A-Za-z\s]*'
        r'(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct|Highway|Hwy|Pike|Circle|Cir)\.?)',
        re.IGNORECASE
    )

    price_pattern = re.compile(r'\$\s*([\d,]+(?:\.\d{2})?)\s*(?:M|K)?', re.IGNORECASE)
    sqft_pattern = re.compile(r'([\d,]+)\s*(?:sq\.?\s*ft|SF|square\s*feet)', re.IGNORECASE)

    for match in address_pattern.finditer(text):
        address = match.group(1).strip()

        # Skip duplicates
        key = address.lower()
        if key in seen:
            continue
        seen.add(key)

        # Get context around the address
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 300)
        context = text[start:end]

        # Extract price
        price = None
        price_numeric = None
        price_match = price_pattern.search(context)
        if price_match:
            try:
                price_str = price_match.group(1).replace(',', '')
                price_numeric = float(price_str)
                # Handle M/K suffixes
                suffix = context[price_match.end():price_match.end()+2].upper()
                if 'M' in suffix:
                    price_numeric *= 1000000
                elif 'K' in suffix:
                    price_numeric *= 1000
                if price_numeric >= 10000:  # Skip obviously wrong prices
                    price = f"${price_numeric:,.0f}"
                else:
                    price = None
                    price_numeric = None
            except:
                pass

        # Extract sqft
        sqft = None
        sqft_numeric = None
        sqft_match = sqft_pattern.search(context)
        if sqft_match:
            try:
                sqft_str = sqft_match.group(1).replace(',', '')
                sqft_numeric = float(sqft_str)
                sqft = f"{sqft_numeric:,.0f} SF"
            except:
                pass

        property_type = determine_property_type(context)

        listings.append(PropertyListing(
            id=f"{source.lower()}_bs_{len(listings)}",
            address=address,
            city=city,
            state=state,
            price=price,
            price_numeric=price_numeric,
            sqft=sqft,
            sqft_numeric=sqft_numeric,
            property_type=property_type,
            source=source.lower(),
            url=None,
        ))

    print(f"[{source}] BeautifulSoup extracted {len(listings)} listings")
    return listings[:20]  # Limit results


def parse_location_from_text(text: str) -> tuple[str, str]:
    """Extract city and state from text."""

    cities = {
        'davenport': 'IA', 'bettendorf': 'IA', 'clinton': 'IA', 'muscatine': 'IA',
        'iowa city': 'IA', 'cedar rapids': 'IA', 'des moines': 'IA',
        'omaha': 'NE', 'lincoln': 'NE',
        'las vegas': 'NV', 'henderson': 'NV', 'reno': 'NV',
        'boise': 'ID', 'nampa': 'ID',
        'moline': 'IL', 'rock island': 'IL', 'east moline': 'IL',
    }

    text_lower = text.lower()

    for city, state in cities.items():
        if city in text_lower:
            return city.title(), state

    state_match = re.search(r'\b(IA|NE|NV|ID|IL)\b', text)
    if state_match:
        return "", state_match.group(1)

    return "", ""


def determine_property_type(text: str) -> str:
    """Determine property type from text."""

    text_lower = text.lower()

    if any(w in text_lower for w in ['land', 'lot', 'acres', 'vacant', 'development']):
        return "land"
    if any(w in text_lower for w in ['office', 'professional']):
        return "office"
    if any(w in text_lower for w in ['warehouse', 'industrial', 'distribution', 'manufacturing']):
        return "industrial"
    if any(w in text_lower for w in ['mixed use', 'mixed-use']):
        return "mixed_use"

    return "retail"


def construct_search_url(address: str, city: str, state: str) -> str:
    """Construct a search URL for a property."""

    full_address = f"{address}, {city}, {state}"
    encoded = urllib.parse.quote(full_address)

    return f"https://www.loopnet.com/search/commercial-real-estate/{city.lower().replace(' ', '-')}-{state.lower()}/for-sale/?sk={encoded}"


async def reverse_geocode_to_city(lat: float, lng: float) -> str:
    """Get city name from coordinates."""

    if not settings.GOOGLE_PLACES_API_KEY:
        return f"{lat:.4f}, {lng:.4f}"

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

                    if city and state:
                        return f"{city}, {state}"
                    elif city:
                        return city
    except Exception as e:
        print(f"[Geocode] Error: {e}")

    return f"{lat:.4f}, {lng:.4f}"


async def geocode_listings(listings: list[PropertyListing]) -> list[PropertyListing]:
    """Add coordinates to listings without them."""

    if not settings.GOOGLE_PLACES_API_KEY:
        return listings

    async with httpx.AsyncClient(timeout=10.0) as client:
        for listing in listings:
            if listing.latitude and listing.longitude:
                continue

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
                print(f"[Geocode] Error for {full_address}: {e}")
                continue

    return listings


def filter_by_radius(
    listings: list[PropertyListing],
    center_lat: float,
    center_lng: float,
    radius_miles: float,
) -> list[PropertyListing]:
    """Filter listings within radius."""
    from math import radians, sin, cos, sqrt, atan2

    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 3959
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return R * 2 * atan2(sqrt(a), sqrt(1-a))

    return [
        l for l in listings
        if l.latitude and l.longitude
        and haversine(center_lat, center_lng, l.latitude, l.longitude) <= radius_miles
    ]


def filter_by_bounds(
    listings: list[PropertyListing],
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
) -> list[PropertyListing]:
    """Filter listings within bounds."""
    return [
        l for l in listings
        if l.latitude and l.longitude
        and min_lat <= l.latitude <= max_lat
        and min_lng <= l.longitude <= max_lng
    ]


def deduplicate_listings(listings: list[PropertyListing]) -> list[PropertyListing]:
    """Remove duplicate listings."""
    seen: set[str] = set()
    unique: list[PropertyListing] = []

    for listing in listings:
        normalized = listing.address.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)

        key = f"{normalized}_{listing.city.lower() if listing.city else ''}"

        if key not in seen:
            seen.add(key)
            unique.append(listing)

    return unique


async def check_api_keys() -> dict:
    """Check configured API keys."""
    return {
        "tavily_configured": settings.TAVILY_API_KEY is not None,
        "anthropic_configured": settings.ANTHROPIC_API_KEY is not None,
        "openai_configured": settings.OPENAI_API_KEY is not None,
        "google_configured": settings.GOOGLE_PLACES_API_KEY is not None,
        "crexi_configured": settings.CREXI_API_KEY is not None,
        # Direct scraping approach only requires Anthropic for AI extraction
        # and Google for geocoding - no Tavily needed
        "all_required_configured": all([
            settings.ANTHROPIC_API_KEY,
            settings.GOOGLE_PLACES_API_KEY,
        ]),
    }
