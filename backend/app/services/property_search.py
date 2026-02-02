"""
Property Search Service

Hybrid approach:
1. Use Tavily to search CRE platforms (regular queries, not site-specific)
2. Extract listing data using Claude AI from search results
3. Scrape actual listing pages when direct URLs are found
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

    Uses hybrid approach:
    1. Tavily search for CRE listings
    2. AI extraction from search results
    3. Page scraping for direct listing URLs
    """
    if not settings.TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY not configured")

    # Get location name for search query
    location_name = await reverse_geocode_to_city(latitude, longitude)

    print(f"[PropertySearch] Starting hybrid search for {location_name}")

    all_listings: list[PropertyListing] = []
    sources_searched: list[str] = []

    # Run multiple search strategies in parallel
    search_tasks = [
        search_with_tavily_and_ai(location_name, "Crexi", property_types),
        search_with_tavily_and_ai(location_name, "LoopNet", property_types),
        search_with_tavily_and_ai(location_name, "General", property_types),
    ]

    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    source_names = ["Crexi", "LoopNet", "General"]
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[PropertySearch] Error searching {source_names[i]}: {result}")
            continue
        # Add to sources_searched even if empty (means search ran successfully)
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


async def search_with_tavily_and_ai(
    location: str,
    source: str,
    property_types: Optional[list[str]] = None,
) -> list[PropertyListing]:
    """Search using Tavily and extract listings with AI."""

    # Build search query based on source
    if source.lower() == "crexi":
        query = f'"{location}" commercial property for sale crexi listing price'
    elif source.lower() == "loopnet":
        query = f'"{location}" commercial real estate for sale loopnet listing'
    else:
        # General search across all CRE sites
        query = f'"{location}" commercial property for sale listing price sqft'

    print(f"[{source}] Searching with query: {query}")

    try:
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
                print(f"[{source}] Tavily search failed: {response.status_code}")
                return []

            data = response.json()
            results = data.get("results", [])

            print(f"[{source}] Tavily returned {len(results)} results")

            if not results:
                return []

            # Try to scrape any direct listing URLs found
            listing_urls = extract_listing_urls(results)
            scraped_listings = []

            if listing_urls:
                print(f"[{source}] Found {len(listing_urls)} direct listing URLs to scrape")
                scraped_listings = await scrape_listing_pages(listing_urls[:5], source, property_types)

            # Also extract listings from search content using AI
            ai_listings = await extract_listings_with_ai(results, source, location)

            # Combine both sources
            all_listings = scraped_listings + ai_listings

            return all_listings

    except Exception as e:
        print(f"[{source}] Search error: {e}")
        return []


def extract_listing_urls(results: list[dict]) -> list[str]:
    """Extract actual listing URLs from search results."""
    urls = []

    listing_patterns = [
        r'crexi\.com/properties/\d+',
        r'loopnet\.com/Listing/\d+',
        r'loopnet\.com/listing/\d+',
        r'commercialcafe\.com/[\w-]+/listing',
        r'cityfeet\.com/[\w-]+/\d+',
    ]

    for result in results:
        url = result.get("url", "")
        content = result.get("content", "") + " " + result.get("raw_content", "")

        # Check if the result URL is a listing
        for pattern in listing_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                urls.append(url)
                break

        # Also search content for listing URLs
        for pattern in listing_patterns:
            matches = re.findall(f'https?://(?:www\\.)?{pattern}[^\\s<>"\']*', content, re.IGNORECASE)
            urls.extend(matches)

    # Deduplicate and limit
    return list(dict.fromkeys(urls))[:10]


async def scrape_listing_pages(
    urls: list[str],
    source: str,
    property_types: Optional[list[str]] = None,
) -> list[PropertyListing]:
    """Scrape listing pages and extract property data."""

    listings = []

    async def fetch_and_parse(url: str, delay: float) -> Optional[PropertyListing]:
        await asyncio.sleep(delay)
        return await fetch_and_parse_listing(url, source)

    tasks = [
        fetch_and_parse(url, i * 0.3)
        for i, url in enumerate(urls)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            continue
        if result:
            if property_types and result.property_type not in property_types:
                continue
            listings.append(result)

    return listings


async def fetch_and_parse_listing(url: str, source: str) -> Optional[PropertyListing]:
    """Fetch a listing page and extract structured data."""

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                return None

            html = response.text

            # Try JSON-LD first
            listing = extract_json_ld_listing(html, url, source)
            if listing:
                return listing

            # Fall back to HTML parsing
            return extract_html_listing(html, url, source)

    except Exception as e:
        print(f"[{source}] Error fetching {url}: {e}")
        return None


def extract_json_ld_listing(html: str, url: str, source: str) -> Optional[PropertyListing]:
    """Extract listing data from JSON-LD structured data."""

    try:
        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')

        for script in scripts:
            try:
                if not script.string:
                    continue
                data = json.loads(script.string)

                if isinstance(data, list):
                    for item in data:
                        listing = parse_json_ld_item(item, url, source)
                        if listing:
                            return listing
                else:
                    listing = parse_json_ld_item(data, url, source)
                    if listing:
                        return listing

            except json.JSONDecodeError:
                continue

        return None

    except Exception:
        return None


def parse_json_ld_item(data: dict, url: str, source: str) -> Optional[PropertyListing]:
    """Parse a JSON-LD item for property data."""

    item_type = data.get("@type", "")

    if item_type not in ["Product", "RealEstateListing", "Place", "LocalBusiness", "Offer", "Thing"]:
        return None

    # Extract address
    address = ""
    city = ""
    state = ""

    address_data = data.get("address", {})
    if isinstance(address_data, dict):
        address = address_data.get("streetAddress", "")
        city = address_data.get("addressLocality", "")
        state = address_data.get("addressRegion", "")
    elif isinstance(address_data, str):
        address = address_data

    if not address:
        address = data.get("name", "")

    if not address or len(address) < 5:
        return None

    # Extract price
    price = None
    price_numeric = None

    offers = data.get("offers", {})
    if isinstance(offers, dict):
        price_val = offers.get("price")
        if price_val:
            try:
                price_numeric = float(price_val)
                price = f"${price_numeric:,.0f}"
            except:
                price = str(price_val)

    # Extract coordinates
    latitude = None
    longitude = None

    geo = data.get("geo", {})
    if isinstance(geo, dict):
        latitude = geo.get("latitude")
        longitude = geo.get("longitude")

    property_type = determine_property_type(
        data.get("description", "") + " " + data.get("name", "")
    )

    return PropertyListing(
        id=f"{source}_{hash(url) % 100000}",
        address=address,
        city=city,
        state=state,
        price=price,
        price_numeric=price_numeric,
        property_type=property_type,
        source=source.lower(),
        url=url,
        latitude=latitude,
        longitude=longitude,
        description=data.get("description", "")[:100] if data.get("description") else None,
    )


def extract_html_listing(html: str, url: str, source: str) -> Optional[PropertyListing]:
    """Extract listing data from HTML."""

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Extract title/address
        address = ""
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            address = title_tag.get_text(strip=True)

        if not address:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                address = og_title.get('content', '')

        # Clean address
        address = re.sub(r'\s*[-|]\s*(Crexi|LoopNet|CoStar).*$', '', address, flags=re.IGNORECASE)
        address = address.strip()

        if not address or len(address) < 5:
            return None

        # Parse city/state
        city, state = parse_location_from_text(address + " " + html[:2000])

        # Extract price
        price = None
        price_numeric = None

        page_text = soup.get_text()
        price_match = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', page_text)
        if price_match:
            try:
                price_str = price_match.group(1).replace(',', '')
                price_numeric = float(price_str)
                price = f"${price_numeric:,.0f}"
            except:
                pass

        # Extract coordinates
        latitude = None
        longitude = None

        lat_match = re.search(r'"lat(?:itude)?"[:\s]*(-?\d+\.\d+)', html)
        lng_match = re.search(r'"(?:lng|longitude)"[:\s]*(-?\d+\.\d+)', html)

        if lat_match and lng_match:
            try:
                latitude = float(lat_match.group(1))
                longitude = float(lng_match.group(1))
            except:
                pass

        property_type = determine_property_type(page_text[:3000])

        return PropertyListing(
            id=f"{source}_{hash(url) % 100000}",
            address=address,
            city=city,
            state=state,
            price=price,
            price_numeric=price_numeric,
            property_type=property_type,
            source=source.lower(),
            url=url,
            latitude=latitude,
            longitude=longitude,
        )

    except Exception:
        return None


async def extract_listings_with_ai(
    search_results: list[dict],
    source: str,
    location: str,
) -> list[PropertyListing]:
    """Use Claude to extract structured property data from search results."""

    if not settings.ANTHROPIC_API_KEY:
        print(f"[{source}] No Anthropic API key, using regex extraction")
        return extract_listings_with_regex(search_results, source, location)

    # Prepare content for AI extraction
    content_text = ""
    for i, result in enumerate(search_results):
        content_text += f"\n--- Result {i+1} ---\n"
        content_text += f"Title: {result.get('title', '')}\n"
        content_text += f"URL: {result.get('url', '')}\n"
        content_text += f"Content: {result.get('content', '')[:2000]}\n"
        raw = result.get('raw_content', '')
        if raw:
            content_text += f"Raw: {raw[:2000]}\n"

    prompt = f"""Extract commercial property listings from these search results for {location}.

Look for ANY property for sale including:
- Retail spaces, storefronts, shopping centers
- Office buildings
- Land, lots, development sites
- Industrial, warehouse
- Mixed-use properties

For each property, extract:
- address: street address (REQUIRED - skip if not found)
- city: city name
- state: 2-letter state code
- price: price as shown (e.g., "$500,000")
- price_numeric: numeric value only, null if unavailable
- sqft: square footage as shown
- sqft_numeric: numeric value only
- property_type: one of: retail, land, office, industrial, mixed_use
- url: the listing URL if found
- description: brief description (max 100 chars)

Return ONLY valid JSON: {{"listings": [...]}}
If no listings found, return: {{"listings": []}}

Search Results:
{content_text}
"""

    try:
        # Use async client for better compatibility with async context
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            system="Extract property listings from search results. Return only valid JSON.",
        )

        content = response.content[0].text

        # Extract JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        listings_data = data.get("listings", data) if isinstance(data, dict) else data

        if not isinstance(listings_data, list):
            return []

        listings = []
        for i, item in enumerate(listings_data):
            if not item.get("address"):
                continue

            # Construct search URL if no listing URL
            url = item.get("url")
            if not url:
                url = construct_search_url(
                    item.get("address", ""),
                    item.get("city", ""),
                    item.get("state", ""),
                )

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
                url=url,
                description=item.get("description"),
            )
            listings.append(listing)

        print(f"[{source}] AI extracted {len(listings)} listings")
        return listings

    except Exception as e:
        print(f"[{source}] AI extraction error: {e}")
        return extract_listings_with_regex(search_results, source, location)


def extract_listings_with_regex(
    search_results: list[dict],
    source: str,
    location: str,
) -> list[PropertyListing]:
    """Fallback regex extraction when AI is unavailable."""

    listings = []
    seen = set()

    # Combine all content
    content = ""
    for result in search_results:
        content += (result.get('content') or '') + "\n"
        content += (result.get('raw_content') or '') + "\n"

    # Pattern: Address with city and state
    address_pattern = re.compile(
        r'(\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct)\.?)'
        r'\s*[,•\-]\s*'
        r'(Davenport|Bettendorf|Moline|Rock Island|Clinton|Muscatine|Iowa City|Cedar Rapids|Des Moines|Omaha|Lincoln|Las Vegas|Henderson|Reno|Boise|Nampa)'
        r'(?:\s*,\s*|\s+)'
        r'(IA|NE|NV|ID|IL)',
        re.IGNORECASE
    )

    price_pattern = re.compile(r'\$\s*([\d,]+(?:\.\d{2})?)', re.IGNORECASE)

    for match in address_pattern.finditer(content):
        street = match.group(1).strip()
        city = match.group(2).strip().title()
        state = match.group(3).upper()

        key = f"{street.lower()}_{city.lower()}"
        if key in seen:
            continue
        seen.add(key)

        # Find nearby price
        price = None
        price_numeric = None
        context = content[max(0, match.start()-100):match.end()+200]
        price_match = price_pattern.search(context)
        if price_match:
            try:
                price_str = price_match.group(1).replace(',', '')
                price_numeric = float(price_str)
                price = f"${price_numeric:,.0f}"
            except:
                pass

        property_type = determine_property_type(context)

        listings.append(PropertyListing(
            id=f"{source.lower()}_regex_{len(listings)}",
            address=street,
            city=city,
            state=state,
            price=price,
            price_numeric=price_numeric,
            property_type=property_type,
            source=source.lower(),
            url=construct_search_url(street, city, state),
        ))

    print(f"[{source}] Regex extracted {len(listings)} listings")
    return listings


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
        "all_required_configured": all([
            settings.TAVILY_API_KEY,
            settings.ANTHROPIC_API_KEY or settings.OPENAI_API_KEY,
        ]),
    }
