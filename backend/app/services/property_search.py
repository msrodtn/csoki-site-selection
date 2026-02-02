"""
Property Search Service

Direct page scraping approach:
1. Use Tavily to find listing URLs from CRE platforms
2. Fetch those pages directly
3. Extract structured data (JSON-LD, Schema.org markup, HTML parsing)
"""

import asyncio
import json
import re
import urllib.parse
from typing import Optional
from pydantic import BaseModel
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

    Uses direct page scraping approach:
    1. Find listing URLs via Tavily site-specific searches
    2. Fetch those pages directly
    3. Extract structured data from pages
    """
    if not settings.TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY not configured")

    # Get location name for search query
    location_name = await reverse_geocode_to_city(latitude, longitude)

    print(f"[PropertySearch] Starting direct scraping search for {location_name}")

    all_listings: list[PropertyListing] = []
    sources_searched: list[str] = []

    # Search each CRE platform directly
    search_tasks = [
        search_crexi_listings(location_name, property_types),
        search_loopnet_listings(location_name, property_types),
        search_commercialcafe_listings(location_name, property_types),
        search_general_listings(location_name, property_types),
    ]

    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    for i, result in enumerate(results):
        source_names = ["Crexi", "LoopNet", "CommercialCafe", "General"]
        if isinstance(result, Exception):
            print(f"[PropertySearch] Error searching {source_names[i]}: {result}")
            continue
        if result:
            all_listings.extend(result)
            sources_searched.append(source_names[i])
            print(f"[PropertySearch] {source_names[i]}: Found {len(result)} listings")

    print(f"[PropertySearch] Total listings before geocoding: {len(all_listings)}")

    # Geocode listings without coordinates
    all_listings = await geocode_listings(all_listings)

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


async def search_crexi_listings(location: str, property_types: Optional[list[str]] = None) -> list[PropertyListing]:
    """Search Crexi for listings using site-specific Tavily search, then scrape pages."""

    query = f'site:crexi.com/properties "{location}" commercial property for sale'

    listing_urls = await find_listing_urls_via_tavily(query, "crexi.com/properties")

    if not listing_urls:
        print(f"[Crexi] No listing URLs found for {location}")
        return []

    print(f"[Crexi] Found {len(listing_urls)} listing URLs to scrape")

    # Scrape each listing page
    listings = await scrape_listing_pages(listing_urls, "crexi", property_types)

    return listings


async def search_loopnet_listings(location: str, property_types: Optional[list[str]] = None) -> list[PropertyListing]:
    """Search LoopNet for listings using site-specific search."""

    query = f'site:loopnet.com/Listing "{location}" commercial property for sale'

    listing_urls = await find_listing_urls_via_tavily(query, "loopnet.com/Listing")

    if not listing_urls:
        print(f"[LoopNet] No listing URLs found for {location}")
        return []

    print(f"[LoopNet] Found {len(listing_urls)} listing URLs to scrape")

    listings = await scrape_listing_pages(listing_urls, "loopnet", property_types)

    return listings


async def search_commercialcafe_listings(location: str, property_types: Optional[list[str]] = None) -> list[PropertyListing]:
    """Search CommercialCafe for listings."""

    query = f'site:commercialcafe.com "{location}" commercial property for sale listing'

    listing_urls = await find_listing_urls_via_tavily(query, "commercialcafe.com")

    if not listing_urls:
        return []

    print(f"[CommercialCafe] Found {len(listing_urls)} listing URLs")

    listings = await scrape_listing_pages(listing_urls, "commercialcafe", property_types)

    return listings


async def search_general_listings(location: str, property_types: Optional[list[str]] = None) -> list[PropertyListing]:
    """Search general CRE sources for listings."""

    # Search for listings across multiple CRE sites
    query = f'"{location}" commercial property for sale listing address price (crexi OR loopnet OR commercialcafe OR cityfeet)'

    if not settings.TAVILY_API_KEY:
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "advanced",
                    "include_raw_content": True,
                    "max_results": 15,
                },
            )

            if response.status_code != 200:
                return []

            data = response.json()
            results = data.get("results", [])

            # Find listing URLs in results
            listing_urls = []
            for result in results:
                url = result.get("url", "")
                if is_likely_listing_url(url):
                    listing_urls.append(url)

            if listing_urls:
                return await scrape_listing_pages(listing_urls[:10], "general", property_types)

            # If no direct listing URLs, try to extract from content
            return await extract_from_search_content(results, location, property_types)

    except Exception as e:
        print(f"[General] Search error: {e}")
        return []


async def find_listing_urls_via_tavily(query: str, url_pattern: str) -> list[str]:
    """Use Tavily to find listing URLs matching a pattern."""

    if not settings.TAVILY_API_KEY:
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 15,
                },
            )

            if response.status_code != 200:
                print(f"[Tavily] Search failed: {response.status_code}")
                return []

            data = response.json()
            results = data.get("results", [])

            # Extract URLs that match the pattern
            urls = []
            for result in results:
                url = result.get("url", "")
                if url_pattern in url.lower() and is_likely_listing_url(url):
                    urls.append(url)

            return urls[:10]  # Limit to 10 URLs to scrape

    except Exception as e:
        print(f"[Tavily] Error: {e}")
        return []


def is_likely_listing_url(url: str) -> bool:
    """Check if URL appears to be an actual listing page, not a search/category page."""
    if not url:
        return False

    url_lower = url.lower()

    # Skip search/category/browse pages
    skip_patterns = [
        '/search', '/results', '/browse', '/category', '/list/',
        '/properties-for-sale', '/commercial-real-estate/', '/all-properties',
        'page=', 'offset=', 'filter=', 'sort='
    ]
    if any(p in url_lower for p in skip_patterns):
        return False

    # Look for listing indicators
    listing_patterns = [
        '/properties/',  # Crexi
        '/listing/',     # LoopNet
        '/property/',    # Generic
        r'\d{6,}',       # Numeric listing ID
    ]

    # Check for listing patterns
    for pattern in listing_patterns:
        if pattern.startswith(r'\\'):
            if re.search(pattern, url):
                return True
        elif pattern in url_lower:
            return True

    return False


async def scrape_listing_pages(urls: list[str], source: str, property_types: Optional[list[str]] = None) -> list[PropertyListing]:
    """Scrape listing pages and extract property data."""

    listings = []

    # Create tasks for concurrent fetching (with rate limiting)
    async def fetch_and_parse(url: str, delay: float) -> Optional[PropertyListing]:
        await asyncio.sleep(delay)  # Stagger requests
        return await fetch_and_parse_listing(url, source)

    tasks = [
        fetch_and_parse(url, i * 0.5)  # 500ms delay between requests
        for i, url in enumerate(urls)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            print(f"[{source}] Scraping error: {result}")
            continue
        if result:
            # Filter by property type if specified
            if property_types and result.property_type not in property_types:
                continue
            listings.append(result)

    return listings


async def fetch_and_parse_listing(url: str, source: str) -> Optional[PropertyListing]:
    """Fetch a listing page and extract structured data."""

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                print(f"[{source}] Failed to fetch {url}: {response.status_code}")
                return None

            html = response.text

            # Try to extract structured data first (JSON-LD)
            listing = extract_json_ld_listing(html, url, source)
            if listing:
                return listing

            # Fall back to HTML parsing
            listing = extract_html_listing(html, url, source)
            return listing

    except Exception as e:
        print(f"[{source}] Error fetching {url}: {e}")
        return None


def extract_json_ld_listing(html: str, url: str, source: str) -> Optional[PropertyListing]:
    """Extract listing data from JSON-LD structured data."""

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Find JSON-LD scripts
        scripts = soup.find_all('script', type='application/ld+json')

        for script in scripts:
            try:
                data = json.loads(script.string)

                # Handle arrays of JSON-LD
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

    except Exception as e:
        print(f"[{source}] JSON-LD extraction error: {e}")
        return None


def parse_json_ld_item(data: dict, url: str, source: str) -> Optional[PropertyListing]:
    """Parse a JSON-LD item for property data."""

    item_type = data.get("@type", "")

    # Handle different Schema.org types
    if item_type in ["Product", "RealEstateListing", "Place", "LocalBusiness", "Offer"]:

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

        # Try other address fields
        if not address:
            address = data.get("streetAddress", "") or data.get("name", "")

        if not address:
            return None

        # Extract price
        price = None
        price_numeric = None

        offers = data.get("offers", {})
        if isinstance(offers, dict):
            price_val = offers.get("price")
            if price_val:
                price_numeric = float(price_val) if isinstance(price_val, (int, float)) else None
                price = f"${price_val:,.0f}" if price_numeric else str(price_val)

        if not price:
            price_str = data.get("price", "")
            if price_str:
                price = str(price_str)
                # Try to extract numeric
                match = re.search(r'[\d,]+(?:\.\d+)?', str(price_str).replace(',', ''))
                if match:
                    try:
                        price_numeric = float(match.group().replace(',', ''))
                    except:
                        pass

        # Extract size
        sqft = None
        sqft_numeric = None

        floor_size = data.get("floorSize", {})
        if isinstance(floor_size, dict):
            sqft_numeric = floor_size.get("value")
            if sqft_numeric:
                sqft = f"{sqft_numeric:,.0f} SF"

        # Extract coordinates
        latitude = None
        longitude = None

        geo = data.get("geo", {})
        if isinstance(geo, dict):
            latitude = geo.get("latitude")
            longitude = geo.get("longitude")

        # Determine property type from description/name
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
            sqft=sqft,
            sqft_numeric=sqft_numeric,
            property_type=property_type,
            source=source,
            url=url,
            latitude=latitude,
            longitude=longitude,
            description=data.get("description", "")[:100] if data.get("description") else None,
        )

    return None


def extract_html_listing(html: str, url: str, source: str) -> Optional[PropertyListing]:
    """Extract listing data from HTML using pattern matching."""

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Extract title/address
        address = ""
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            address = title_tag.get_text(strip=True)

        # Try meta tags
        if not address:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                address = og_title.get('content', '')

        # Clean up address - remove site name
        address = re.sub(r'\s*[-|]\s*(Crexi|LoopNet|CommercialCafe|CoStar).*$', '', address, flags=re.IGNORECASE)
        address = address.strip()

        if not address or len(address) < 5:
            return None

        # Parse city/state from address
        city, state = parse_location_from_text(address + " " + html[:2000])

        # Extract price from page
        price = None
        price_numeric = None

        price_patterns = [
            r'\$\s*([\d,]+(?:\.\d{2})?)\s*(?:USD)?',
            r'Price[:\s]*\$\s*([\d,]+)',
            r'Asking[:\s]*\$\s*([\d,]+)',
        ]

        page_text = soup.get_text()
        for pattern in price_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    price_numeric = float(price_str)
                    price = f"${price_numeric:,.0f}"
                    break
                except:
                    continue

        # Extract square footage
        sqft = None
        sqft_numeric = None

        sqft_patterns = [
            r'([\d,]+)\s*(?:sq\.?\s*ft\.?|SF|square\s*feet)',
            r'Size[:\s]*([\d,]+)',
        ]

        for pattern in sqft_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                sqft_str = match.group(1).replace(',', '')
                try:
                    sqft_numeric = float(sqft_str)
                    sqft = f"{sqft_numeric:,.0f} SF"
                    break
                except:
                    continue

        # Extract coordinates from page
        latitude = None
        longitude = None

        # Look for coordinates in various formats
        coord_patterns = [
            r'"lat(?:itude)?"[:\s]*(-?\d+\.\d+)',
            r'"lng|longitude"[:\s]*(-?\d+\.\d+)',
            r'data-lat[=:"]+(-?\d+\.\d+)',
            r'data-lng[=:"]+(-?\d+\.\d+)',
        ]

        lat_match = re.search(coord_patterns[0], html)
        lng_match = re.search(coord_patterns[1], html)

        if lat_match and lng_match:
            try:
                latitude = float(lat_match.group(1))
                longitude = float(lng_match.group(1))
            except:
                pass

        # Determine property type
        property_type = determine_property_type(page_text[:3000])

        # Get description
        description = None
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            description = desc_tag.get('content', '')[:100]

        return PropertyListing(
            id=f"{source}_{hash(url) % 100000}",
            address=address,
            city=city,
            state=state,
            price=price,
            price_numeric=price_numeric,
            sqft=sqft,
            sqft_numeric=sqft_numeric,
            property_type=property_type,
            source=source,
            url=url,
            latitude=latitude,
            longitude=longitude,
            description=description,
        )

    except Exception as e:
        print(f"[{source}] HTML extraction error: {e}")
        return None


async def extract_from_search_content(results: list[dict], location: str, property_types: Optional[list[str]] = None) -> list[PropertyListing]:
    """Extract listings from Tavily search result content when no direct URLs found."""

    listings = []

    # Combine all content
    content = ""
    for result in results:
        content += (result.get('content') or '') + "\n"
        content += (result.get('raw_content') or '') + "\n"

    # Use regex patterns to extract listings
    # Pattern: Address followed by price and/or size
    listing_pattern = re.compile(
        r'(\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct)\.?)'
        r'[,\s]+([A-Za-z\s]+)'  # City
        r'[,\s]+([A-Z]{2})'  # State
        r'.*?'
        r'(?:\$\s*([\d,]+))?',  # Optional price
        re.IGNORECASE | re.DOTALL
    )

    seen = set()

    for match in listing_pattern.finditer(content):
        address = match.group(1).strip()
        city = match.group(2).strip().title()
        state = match.group(3).upper()
        price_str = match.group(4)

        # Skip duplicates
        key = f"{address.lower()}_{city.lower()}"
        if key in seen:
            continue
        seen.add(key)

        price = None
        price_numeric = None
        if price_str:
            try:
                price_numeric = float(price_str.replace(',', ''))
                price = f"${price_numeric:,.0f}"
            except:
                pass

        property_type = determine_property_type(content[max(0, match.start()-100):match.end()+200])

        if property_types and property_type not in property_types:
            continue

        listings.append(PropertyListing(
            id=f"general_{len(listings)}_{hash(address) % 10000}",
            address=address,
            city=city,
            state=state,
            price=price,
            price_numeric=price_numeric,
            property_type=property_type,
            source="general",
            url=construct_search_url(address, city, state),
        ))

    return listings


def parse_location_from_text(text: str) -> tuple[str, str]:
    """Extract city and state from text."""

    # Target market cities
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

    # Try to find state pattern
    state_match = re.search(r'\b(IA|NE|NV|ID|IL)\b', text)
    if state_match:
        return "", state_match.group(1)

    return "", ""


def determine_property_type(text: str) -> str:
    """Determine property type from descriptive text."""

    text_lower = text.lower()

    if any(w in text_lower for w in ['land', 'lot', 'acres', 'vacant', 'development site']):
        return "land"
    if any(w in text_lower for w in ['office', 'professional']):
        return "office"
    if any(w in text_lower for w in ['warehouse', 'industrial', 'distribution', 'manufacturing', 'flex']):
        return "industrial"
    if any(w in text_lower for w in ['mixed use', 'mixed-use', 'live/work']):
        return "mixed_use"

    return "retail"  # Default


def construct_search_url(address: str, city: str, state: str) -> str:
    """Construct a search URL for finding a specific property."""

    full_address = f"{address}, {city}, {state}"
    encoded = urllib.parse.quote(full_address)

    # Default to LoopNet search
    return f"https://www.loopnet.com/search/commercial-real-estate/{city.lower().replace(' ', '-')}-{state.lower()}/for-sale/?sk={encoded}"


async def reverse_geocode_to_city(lat: float, lng: float) -> str:
    """Get city/area name from coordinates using Google Geocoding API."""

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
        print(f"[Geocode] Reverse geocoding error: {e}")

    return f"{lat:.4f}, {lng:.4f}"


async def geocode_listings(listings: list[PropertyListing]) -> list[PropertyListing]:
    """Add coordinates to listings that don't have them."""

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
    """Filter listings to those within the specified radius."""
    from math import radians, sin, cos, sqrt, atan2

    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 3959  # Earth's radius in miles
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    return [
        listing for listing in listings
        if listing.latitude and listing.longitude
        and haversine_distance(center_lat, center_lng, listing.latitude, listing.longitude) <= radius_miles
    ]


def filter_by_bounds(
    listings: list[PropertyListing],
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
) -> list[PropertyListing]:
    """Filter listings to those within map viewport bounds."""
    return [
        listing for listing in listings
        if listing.latitude and listing.longitude
        and min_lat <= listing.latitude <= max_lat
        and min_lng <= listing.longitude <= max_lng
    ]


def deduplicate_listings(listings: list[PropertyListing]) -> list[PropertyListing]:
    """Remove duplicate listings based on address similarity."""
    seen: set[str] = set()
    unique: list[PropertyListing] = []

    for listing in listings:
        # Normalize address
        normalized = listing.address.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)

        key = f"{normalized}_{listing.city.lower() if listing.city else ''}"

        if key not in seen:
            seen.add(key)
            unique.append(listing)

    return unique


async def check_api_keys() -> dict:
    """Check which API keys are configured for property search."""
    return {
        "tavily_configured": settings.TAVILY_API_KEY is not None,
        "anthropic_configured": settings.ANTHROPIC_API_KEY is not None,
        "openai_configured": settings.OPENAI_API_KEY is not None,
        "google_configured": settings.GOOGLE_PLACES_API_KEY is not None,
        "crexi_configured": settings.CREXI_API_KEY is not None,
        "all_required_configured": all([
            settings.TAVILY_API_KEY,
            settings.GOOGLE_PLACES_API_KEY,  # Needed for geocoding
        ]),
    }
