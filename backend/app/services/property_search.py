"""
Property Search Service

Uses AI-powered web search to find commercial real estate listings
from multiple sources (Crexi, LoopNet, Zillow Commercial, etc.)
"""

import json
import re
import urllib.parse
from typing import Optional
from pydantic import BaseModel
import anthropic
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

    print(f"[PropertySearch] Total listings after geocoding: {len(all_listings)}")
    for listing in all_listings[:5]:
        print(f"  - {listing.address}, {listing.city}, {listing.state} | lat={listing.latitude}, lng={listing.longitude}")

    # Filter to listings within radius (use larger radius to avoid filtering too aggressively)
    # Use 50 miles as minimum to ensure we capture listings
    effective_radius = max(radius_miles, 50)
    filtered_listings = filter_by_radius(
        listings=all_listings,
        center_lat=latitude,
        center_lng=longitude,
        radius_miles=effective_radius,
    )

    print(f"[PropertySearch] Listings within {effective_radius} miles: {len(filtered_listings)}")

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


def construct_property_search_url(address: str, city: str, state: str, source: str) -> str:
    """Construct a search URL for major CRE platforms based on address."""
    full_address = f"{address}, {city}, {state}"
    encoded_address = urllib.parse.quote(full_address)

    # Create platform-specific search URLs
    source_lower = source.lower()
    if 'crexi' in source_lower:
        return f"https://www.crexi.com/search?q={encoded_address}"
    elif 'loopnet' in source_lower:
        # LoopNet search URL format
        location_slug = f"{city}-{state}".lower().replace(' ', '-')
        return f"https://www.loopnet.com/search/commercial-real-estate/{location_slug}/for-sale/?sk={encoded_address}"
    else:
        # Default to Google search for the specific property listing
        return f"https://www.google.com/search?q={encoded_address}+commercial+property+for+sale"


async def extract_listings_with_ai(
    search_results: list[dict],
    source: str,
    location: str,
) -> list[PropertyListing]:
    """Use Claude to extract structured property data from search results."""

    # Check for Anthropic API key first, fall back to OpenAI
    if not settings.ANTHROPIC_API_KEY:
        print(f"[PropertySearch] No Anthropic API key, falling back to regex for {source}")
        return extract_listings_with_regex(search_results, source, location)

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Prepare content for AI extraction
    content_text = ""
    for i, result in enumerate(search_results):
        r_title = result.get('title') or ''
        r_url = result.get('url') or ''
        r_content = result.get('content') or ''
        r_raw = result.get('raw_content') or ''
        content_text += f"\n--- Result {i+1} ---\n"
        content_text += f"Title: {r_title}\n"
        content_text += f"URL: {r_url}\n"
        content_text += f"Content: {r_content[:1500]}\n"
        if r_raw:
            content_text += f"Raw Content: {r_raw[:2000]}\n"

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
- url: Look for specific listing URLs in the content. Valid URLs include patterns like:
  * crexi.com/properties/[id-or-slug]
  * loopnet.com/Listing/[id]/[address-slug]
  * Any URL with /property/, /listing/, /properties/ that includes a property ID or MLS number
  If you find such a URL, use it. If you can only find general search/category pages, set url to null (we'll construct a search URL later).
- description: brief description (max 100 chars)

Be generous in extraction - if you see something that looks like a property listing with an address and price, include it.

Return ONLY valid JSON in this exact format: {{"listings": [...]}}
If no listings found, return: {{"listings": []}}

Search Results:
{content_text}
"""

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ],
            system="You are a data extraction assistant. Extract structured property listing data from web search results. Return only valid JSON, no other text.",
        )

        content = response.content[0].text

        # Extract JSON from response (Claude might include markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        data = json.loads(content)

        # Handle both {"listings": [...]} and direct array formats
        listings_data = data.get("listings", data) if isinstance(data, dict) else data

        if not isinstance(listings_data, list):
            return []

        listings = []
        for i, item in enumerate(listings_data):
            if not item.get("address"):
                continue

            # Get extracted URL, or construct a search URL if none found
            extracted_url = item.get("url")
            if not extracted_url:
                # Construct a useful search URL for this specific property
                extracted_url = construct_property_search_url(
                    address=item.get("address", ""),
                    city=item.get("city", ""),
                    state=item.get("state", ""),
                    source=source,
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
                url=extracted_url,
                description=item.get("description"),
            )
            listings.append(listing)

        return listings

    except Exception as e:
        print(f"AI extraction error: {e}")
        # Fall back to regex extraction
        print(f"[PropertySearch] Falling back to regex extraction for {source}")
        return extract_listings_with_regex(search_results, source, location)


def extract_listings_with_regex(
    search_results: list[dict],
    source: str,
    location: str,
) -> list[PropertyListing]:
    """
    Fallback regex-based extraction when AI is unavailable.
    Looks for common patterns in commercial real estate listings.
    """
    listings = []
    listing_id = 0

    # Common address patterns - more specific to avoid capturing partial matches
    # Pattern: "123 Street Name, City, ST" or "123 Street Name • City, ST"
    address_pattern = re.compile(
        r'(\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct)\.?)'
        r'\s*[,•\-]\s*'
        r'(Davenport|Bettendorf|Moline|Rock Island|East Moline|Clinton|Muscatine|Iowa City|Cedar Rapids|Des Moines|Omaha|Lincoln|Las Vegas|Henderson|Reno|Boise|Nampa)'
        r'(?:\s*,\s*|\s+)'
        r'(IA|Iowa|NE|Nebraska|NV|Nevada|ID|Idaho|IL|Illinois)',
        re.IGNORECASE
    )

    # Price patterns - match standalone prices, not prices merged with other numbers
    price_pattern = re.compile(
        r'\$\s*([\d,]+(?:\.\d{2})?)\s*(?:/(?:SqFt|SF|sq\s*ft))?(?!\d)',
        re.IGNORECASE
    )

    # Square footage patterns
    sqft_pattern = re.compile(
        r'([\d,]+)\s*(?:sq\s*ft|SF|square\s*feet)',
        re.IGNORECASE
    )

    # Acreage patterns
    acres_pattern = re.compile(
        r'([\d.]+)\s*acres?',
        re.IGNORECASE
    )

    seen_addresses = set()

    # Expanded pattern to find specific listing URLs (matches slugs, not just numeric IDs)
    listing_url_patterns = [
        # Crexi - matches /properties/ followed by ID and optional slug
        re.compile(r'https?://(?:www\.)?crexi\.com/properties/[\w-]+', re.IGNORECASE),
        # LoopNet - matches /Listing/ with ID and optional address slug
        re.compile(r'https?://(?:www\.)?loopnet\.com/Listing/[\w/-]+', re.IGNORECASE),
        # CommercialCafe
        re.compile(r'https?://(?:www\.)?commercialcafe\.com/[\w/-]*listing[\w/-]+', re.IGNORECASE),
        # CityFeet
        re.compile(r'https?://(?:www\.)?cityfeet\.com/[\w/-]*(?:listing|commercial)[\w/-]+', re.IGNORECASE),
        # Zillow Commercial
        re.compile(r'https?://(?:www\.)?zillow\.com/commercial/[\w/-]+', re.IGNORECASE),
        # CoStar/Ten-X
        re.compile(r'https?://(?:www\.)?ten-x\.com/[\w/-]*property[\w/-]+', re.IGNORECASE),
        # Generic pattern for URLs with property identifiers
        re.compile(r'https?://[\w.-]+/(?:property|listing|commercial|properties|listings)/[\w-]+\d+[\w-]*', re.IGNORECASE),
    ]

    def construct_search_url(address: str, city: str, state: str, source: str) -> str:
        """Construct a search URL for major CRE platforms based on address."""
        # Use the module-level function
        return construct_property_search_url(address, city, state, source)

    def find_specific_listing_url(content: str, address: str, city: str, state: str, source: str, fallback_url: str) -> str:
        """Try to find a specific listing URL in the content for this property."""
        # First look for URLs matching known CRE listing patterns
        for pattern in listing_url_patterns:
            matches = pattern.findall(content)
            if matches:
                # Return the first match that looks like a real listing
                for match in matches:
                    # Skip URLs that are just category pages
                    if not any(skip in match.lower() for skip in ['/search', '/results', '/browse', '/category']):
                        return match

        # Look for any URL in content that might be a listing
        all_urls = re.findall(r'https?://[^\s<>"\')\]]+', content)
        for url in all_urls:
            url_lower = url.lower()
            # Check for listing indicators
            if any(x in url_lower for x in ['/property/', '/listing/', '/properties/', '/listings/', 'mls=', 'propertyid=', 'pid=']):
                # Skip search/category pages
                if not any(skip in url_lower for skip in ['/search', '/results', '/browse', '/category', 'property-search']):
                    return url.rstrip('.,;:')

        # If no specific listing URL found, construct a search URL for this exact property
        # This is better than linking to a general category page
        return construct_search_url(address, city, state, source)

    def normalize_address(addr: str, city: str) -> str:
        """Normalize address for deduplication."""
        # Remove leading zeros from street numbers
        addr = re.sub(r'^0+(\d)', r'\1', addr)
        # Remove street suffix variations
        addr = re.sub(r'\s+(Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct)\.?$', '', addr, flags=re.IGNORECASE)
        # Normalize whitespace
        addr = re.sub(r'\s+', ' ', addr).strip().lower()
        return f"{addr}_{city.lower()}"

    # Alternative pattern: "$price Street Number Street Name • City, ST"
    # Handle case where price and street number run together: "$820,0003709 N Harrison"
    # In this case "820,000" is price and "3709" is street number
    price_address_pattern = re.compile(
        r'\$\s*([\d,]+(?:\.\d{2})?)\s+'  # Price followed by whitespace
        r'(\d{1,5}\s+(?:[NSEW]\.?\s+)?[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct)\.?)'
        r'\s*[,•\-]\s*'
        r'(Davenport|Bettendorf|Moline|Rock Island|Clinton|Muscatine|Iowa City|Cedar Rapids|Des Moines|Omaha|Lincoln|Las Vegas|Henderson|Reno|Boise|Nampa)',
        re.IGNORECASE
    )

    # Pattern for parsing concatenated price+street (common in listing scraped text)
    # e.g., "$820,0003709 N Harrison Street" -> price=$820,000, street=3709 N Harrison Street
    concat_pattern = re.compile(
        r'\$\s*([\d,]+,\d{3})(\d{2,5})\s+(?:([NSEW]\.?\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct)\.?)'
        r'\s*[,•\-]?\s*'
        r'(Davenport|Bettendorf|Moline|Rock Island|Clinton|Muscatine|Iowa City|Cedar Rapids|Des Moines|Omaha|Lincoln)',
        re.IGNORECASE
    )

    for result in search_results:
        content = (result.get('content') or '') + ' ' + (result.get('raw_content') or '')
        url = result.get('url') or ''

        # First try to parse concatenated price+street patterns
        for match in concat_pattern.finditer(content):
            price_str = match.group(1)  # e.g., "820,000"
            street_num = match.group(2)  # e.g., "3709"
            direction = match.group(3) or ''
            street_name = match.group(4)
            city = match.group(5).strip().title()

            # Reconstruct the full street address
            street = f"{street_num} {direction}{street_name}"
            street = re.sub(r'\s+', ' ', street).strip()

            # Determine state from city
            state = 'IA'
            if city.lower() in ['omaha', 'lincoln']:
                state = 'NE'
            elif city.lower() in ['moline', 'rock island']:
                state = 'IL'

            addr_key = normalize_address(street, city)
            if addr_key in seen_addresses:
                continue
            seen_addresses.add(addr_key)

            price = f"${price_str}"
            try:
                price_numeric = float(price_str.replace(',', ''))
            except:
                price_numeric = None

            # Look for sqft nearby
            sqft = None
            sqft_numeric = None
            match_pos = match.start()
            context = content[max(0, match_pos-50):match_pos+250]
            sqft_match = sqft_pattern.search(context)
            if sqft_match:
                sqft_str = sqft_match.group(1)
                sqft = f"{sqft_str} SF"
                try:
                    sqft_numeric = float(sqft_str.replace(',', ''))
                except:
                    pass

            if not sqft:
                acres_match = acres_pattern.search(context)
                if acres_match:
                    sqft = f"{acres_match.group(1)} acres"

            # Determine property type
            property_type = "retail"
            context_lower = context.lower()
            if any(word in context_lower for word in ['land', 'lot', 'acres', 'vacant']):
                property_type = "land"
            elif 'office' in context_lower:
                property_type = "office"
            elif any(word in context_lower for word in ['warehouse', 'industrial']):
                property_type = "industrial"

            # Try to find a specific listing URL for this property
            specific_url = find_specific_listing_url(content, street, city, state, source, url)

            listing = PropertyListing(
                id=f"{source.lower()}_regex_{listing_id}",
                address=street,
                city=city,
                state=state,
                price=price,
                price_numeric=price_numeric,
                sqft=sqft,
                sqft_numeric=sqft_numeric,
                property_type=property_type,
                source=source.lower(),
                url=specific_url,
                description=f"{street}, {city} - {price}"[:100],
            )
            listings.append(listing)
            listing_id += 1

        # Then try the price+address pattern (space-separated)
        for match in price_address_pattern.finditer(content):
            price_str = match.group(1)
            street = match.group(2).strip()
            city = match.group(3).strip().title()

            # Determine state from city
            state = 'IA'  # Default
            if city.lower() in ['omaha', 'lincoln']:
                state = 'NE'
            elif city.lower() in ['las vegas', 'henderson', 'reno']:
                state = 'NV'
            elif city.lower() in ['boise', 'nampa']:
                state = 'ID'
            elif city.lower() in ['moline', 'rock island', 'east moline']:
                state = 'IL'

            addr_key = normalize_address(street, city)
            if addr_key in seen_addresses:
                continue
            seen_addresses.add(addr_key)

            price = f"${price_str}"
            try:
                price_numeric = float(price_str.replace(',', ''))
            except:
                price_numeric = None

            # Look for sqft nearby
            sqft = None
            sqft_numeric = None
            match_pos = match.start()
            context = content[max(0, match_pos-50):match_pos+250]
            sqft_match = sqft_pattern.search(context)
            if sqft_match:
                sqft_str = sqft_match.group(1)
                sqft = f"{sqft_str} SF"
                try:
                    sqft_numeric = float(sqft_str.replace(',', ''))
                except:
                    pass

            # Determine property type
            property_type = "retail"
            context_lower = context.lower()
            if any(word in context_lower for word in ['land', 'lot', 'acres', 'vacant']):
                property_type = "land"
            elif any(word in context_lower for word in ['office']):
                property_type = "office"
            elif any(word in context_lower for word in ['warehouse', 'industrial']):
                property_type = "industrial"

            # Try to find a specific listing URL for this property
            specific_url = find_specific_listing_url(content, street, city, state, source, url)

            listing = PropertyListing(
                id=f"{source.lower()}_regex_{listing_id}",
                address=street,
                city=city,
                state=state,
                price=price,
                price_numeric=price_numeric,
                sqft=sqft,
                sqft_numeric=sqft_numeric,
                property_type=property_type,
                source=source.lower(),
                url=specific_url,
                description=f"{street}, {city} - {price}"[:100],
            )
            listings.append(listing)
            listing_id += 1

        # Then try the address-only pattern
        for match in address_pattern.finditer(content):
            street = match.group(1).strip()
            city = match.group(2).strip().title()
            state = match.group(3).strip().upper()

            # Normalize state
            state_map = {'IOWA': 'IA', 'NEBRASKA': 'NE', 'NEVADA': 'NV', 'IDAHO': 'ID', 'ILLINOIS': 'IL'}
            state = state_map.get(state, state)

            # Skip if we've seen this address
            addr_key = normalize_address(street, city)
            if addr_key in seen_addresses:
                continue
            seen_addresses.add(addr_key)

            # Search for price near the address
            price = None
            price_numeric = None
            # Look for price within 200 chars of address
            addr_pos = match.start()
            context = content[max(0, addr_pos-100):addr_pos+300]
            price_match = price_pattern.search(context)
            if price_match:
                price_str = price_match.group(1) or price_match.group(2)
                if price_str:
                    price = f"${price_str}"
                    try:
                        price_numeric = float(price_str.replace(',', ''))
                    except:
                        pass

            # Search for sqft near the address
            sqft = None
            sqft_numeric = None
            sqft_match = sqft_pattern.search(context)
            if sqft_match:
                sqft_str = sqft_match.group(1)
                sqft = f"{sqft_str} SF"
                try:
                    sqft_numeric = float(sqft_str.replace(',', ''))
                except:
                    pass

            # Check for acreage if no sqft
            if not sqft:
                acres_match = acres_pattern.search(context)
                if acres_match:
                    sqft = f"{acres_match.group(1)} acres"

            # Determine property type from context
            property_type = "retail"  # default
            context_lower = context.lower()
            if any(word in context_lower for word in ['land', 'lot', 'acres', 'vacant']):
                property_type = "land"
            elif any(word in context_lower for word in ['office']):
                property_type = "office"
            elif any(word in context_lower for word in ['warehouse', 'industrial', 'distribution']):
                property_type = "industrial"
            elif any(word in context_lower for word in ['mixed use', 'mixed-use']):
                property_type = "mixed_use"

            # Try to find a specific listing URL for this property
            specific_url = find_specific_listing_url(content, street, city, state, source, url)

            listing = PropertyListing(
                id=f"{source.lower()}_regex_{listing_id}",
                address=street,
                city=city,
                state=state,
                price=price,
                price_numeric=price_numeric,
                sqft=sqft,
                sqft_numeric=sqft_numeric,
                property_type=property_type,
                source=source.lower(),
                url=specific_url,
                description=f"Property at {street}, {city}"[:100],
            )
            listings.append(listing)
            listing_id += 1

    print(f"[PropertySearch] Regex extraction found {len(listings)} listings from {source}")
    return listings


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
        "anthropic_configured": settings.ANTHROPIC_API_KEY is not None,
        "openai_configured": settings.OPENAI_API_KEY is not None,
        "google_configured": settings.GOOGLE_PLACES_API_KEY is not None,
        "crexi_configured": settings.CREXI_API_KEY is not None,
        "all_required_configured": all([
            settings.TAVILY_API_KEY,
            settings.ANTHROPIC_API_KEY or settings.OPENAI_API_KEY,  # Either AI provider works
        ]),
    }
