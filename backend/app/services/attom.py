"""
ATTOM Property Data Service

Integrates with ATTOM's Property API to provide:
- Property search by geographic area
- Ownership and transaction history
- "Opportunity" signals (likelihood to sell indicators)
- Property details for the Properties For Sale layer

ATTOM API Documentation: https://api.developer.attomdata.com/docs
"""

import httpx
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timedelta
from enum import Enum

from ..core.config import settings


# =============================================================================
# Data Models
# =============================================================================

class PropertyType(str, Enum):
    """Property type classifications."""
    RETAIL = "retail"
    LAND = "land"
    OFFICE = "office"
    INDUSTRIAL = "industrial"
    MIXED_USE = "mixed_use"
    UNKNOWN = "unknown"


class PropertySource(str, Enum):
    """Data source for property listing."""
    ATTOM = "attom"
    REPORTALL = "reportall"
    QUANTUMLISTING = "quantumlisting"
    TEAM_CONTRIBUTED = "team_contributed"


class OpportunitySignal(BaseModel):
    """A signal indicating likelihood to sell."""
    signal_type: str  # e.g., "tax_delinquent", "owner_age", "vacancy", "distress"
    description: str
    strength: str  # "high", "medium", "low"


class PropertyListing(BaseModel):
    """A property listing from ATTOM or other sources."""
    id: str
    address: str
    city: str
    state: str
    zip_code: Optional[str] = None
    latitude: float
    longitude: float

    # Listing details
    property_type: PropertyType = PropertyType.UNKNOWN
    price: Optional[float] = None
    price_display: Optional[str] = None  # Formatted price string
    sqft: Optional[float] = None
    lot_size_acres: Optional[float] = None
    year_built: Optional[int] = None

    # Ownership
    owner_name: Optional[str] = None
    owner_type: Optional[str] = None  # "individual", "corporate", "trust", etc.

    # Valuation
    assessed_value: Optional[float] = None
    market_value: Optional[float] = None

    # Transaction history
    last_sale_date: Optional[str] = None
    last_sale_price: Optional[float] = None

    # Source and status
    source: PropertySource = PropertySource.ATTOM
    listing_type: str = "opportunity"  # "active_listing" or "opportunity"

    # Opportunity signals (for predictive properties)
    opportunity_signals: List[OpportunitySignal] = []
    opportunity_score: Optional[float] = None  # 0-100 score

    # External links
    external_url: Optional[str] = None

    # Raw data for debugging
    raw_data: Optional[dict] = None


class PropertySearchResult(BaseModel):
    """Result of a property search."""
    center_latitude: float
    center_longitude: float
    radius_miles: float
    properties: List[PropertyListing]
    total_found: int
    sources: List[str]
    search_timestamp: str


class GeoBounds(BaseModel):
    """Geographic bounding box."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


# =============================================================================
# ATTOM API Client
# =============================================================================

ATTOM_BASE_URL = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"


def _get_headers() -> dict:
    """Get headers for ATTOM API requests."""
    if not settings.ATTOM_API_KEY:
        raise ValueError("ATTOM_API_KEY not configured")

    return {
        "apikey": settings.ATTOM_API_KEY,
        "Accept": "application/json",
    }


def _classify_property_type(use_code: Optional[str], land_use: Optional[str]) -> PropertyType:
    """
    Classify property type based on ATTOM use codes.

    ATTOM uses standardized property use codes. Common commercial codes:
    - 300-399: Commercial
    - 400-499: Industrial
    - 500-599: Agricultural/Rural
    - 700-799: Vacant Land
    """
    if not use_code and not land_use:
        return PropertyType.UNKNOWN

    code_str = str(use_code or "").lower()
    land_str = str(land_use or "").lower()
    combined = f"{code_str} {land_str}"

    # Retail indicators
    if any(x in combined for x in ["retail", "store", "shop", "restaurant", "commercial"]):
        return PropertyType.RETAIL

    # Office indicators
    if any(x in combined for x in ["office", "professional"]):
        return PropertyType.OFFICE

    # Industrial indicators
    if any(x in combined for x in ["industrial", "warehouse", "manufacturing", "distribution"]):
        return PropertyType.INDUSTRIAL

    # Land indicators
    if any(x in combined for x in ["vacant", "land", "lot", "undeveloped"]):
        return PropertyType.LAND

    # Mixed use indicators
    if any(x in combined for x in ["mixed", "multi-use"]):
        return PropertyType.MIXED_USE

    return PropertyType.UNKNOWN


def _calculate_opportunity_signals(property_data: dict) -> tuple[List[OpportunitySignal], float]:
    """
    Calculate opportunity signals and score based on property data.

    Returns (signals_list, opportunity_score)
    """
    signals = []
    score = 0.0

    # Check for tax delinquency
    tax_delinquent = property_data.get("assessment", {}).get("taxDelinquent")
    if tax_delinquent:
        signals.append(OpportunitySignal(
            signal_type="tax_delinquent",
            description="Property has delinquent taxes",
            strength="high"
        ))
        score += 25

    # Check for foreclosure/pre-foreclosure status
    foreclosure_status = property_data.get("sale", {}).get("foreclosureStatus")
    if foreclosure_status:
        signals.append(OpportunitySignal(
            signal_type="distress",
            description=f"Foreclosure status: {foreclosure_status}",
            strength="high"
        ))
        score += 30

    # Check ownership duration (long-term owners more likely to sell)
    last_sale = property_data.get("sale", {}).get("saleTransDate")
    if last_sale:
        try:
            sale_date = datetime.strptime(last_sale[:10], "%Y-%m-%d")
            years_owned = (datetime.now() - sale_date).days / 365
            if years_owned > 15:
                signals.append(OpportunitySignal(
                    signal_type="long_term_owner",
                    description=f"Same owner for {int(years_owned)}+ years",
                    strength="medium"
                ))
                score += 15
        except (ValueError, TypeError):
            pass

    # Check for corporate vs individual ownership (estates, trusts = opportunity)
    owner_type = property_data.get("assessment", {}).get("ownerType", "").lower()
    if "trust" in owner_type or "estate" in owner_type:
        signals.append(OpportunitySignal(
            signal_type="estate_ownership",
            description="Owned by trust or estate",
            strength="medium"
        ))
        score += 20

    # Check assessed vs market value gap (undervalued = opportunity)
    assessed = property_data.get("assessment", {}).get("assessedValue")
    market = property_data.get("avm", {}).get("amount", {}).get("value")
    if assessed and market and market > 0:
        ratio = assessed / market
        if ratio < 0.7:  # Assessed at less than 70% of market
            signals.append(OpportunitySignal(
                signal_type="undervalued",
                description=f"Assessed {int(ratio*100)}% below market value",
                strength="medium"
            ))
            score += 10

    # Cap score at 100
    score = min(score, 100)

    return signals, score


def _format_price(price: Optional[float]) -> Optional[str]:
    """Format price as display string."""
    if not price:
        return None
    if price >= 1_000_000:
        return f"${price/1_000_000:.1f}M"
    elif price >= 1_000:
        return f"${price/1_000:.0f}K"
    else:
        return f"${price:,.0f}"


async def search_properties_by_bounds(
    bounds: GeoBounds,
    property_types: Optional[List[PropertyType]] = None,
    min_opportunity_score: float = 0,
    limit: int = 50,
) -> PropertySearchResult:
    """
    Search for properties within geographic bounds.

    Uses ATTOM's Property API to find properties and enriches with
    opportunity signals.
    """
    if not settings.ATTOM_API_KEY:
        raise ValueError("ATTOM_API_KEY not configured")

    # Calculate center point for result metadata
    center_lat = (bounds.min_lat + bounds.max_lat) / 2
    center_lng = (bounds.min_lng + bounds.max_lng) / 2

    # Approximate radius in miles
    lat_diff = bounds.max_lat - bounds.min_lat
    lng_diff = bounds.max_lng - bounds.min_lng
    approx_radius = max(lat_diff, lng_diff) * 69 / 2  # 1 degree ≈ 69 miles

    properties = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # ATTOM Property Search by Geographic Area
            # Using the area endpoint with geoIdV4 parameter
            response = await client.get(
                f"{ATTOM_BASE_URL}/property/snapshot",
                headers=_get_headers(),
                params={
                    "minLatitude": bounds.min_lat,
                    "maxLatitude": bounds.max_lat,
                    "minLongitude": bounds.min_lng,
                    "maxLongitude": bounds.max_lng,
                    "propertytype": "COMMERCIAL",  # Filter to commercial properties
                    "pagesize": limit,
                },
            )

            if response.status_code == 200:
                data = response.json()
                property_list = data.get("property", [])

                for prop in property_list:
                    try:
                        # Extract address info
                        address_info = prop.get("address", {})
                        location_info = prop.get("location", {})
                        assessment_info = prop.get("assessment", {})
                        sale_info = prop.get("sale", {})
                        building_info = prop.get("building", {})
                        lot_info = prop.get("lot", {})

                        # Get coordinates
                        lat = location_info.get("latitude")
                        lng = location_info.get("longitude")

                        if not lat or not lng:
                            continue

                        # Classify property type
                        use_code = assessment_info.get("propertyType")
                        land_use = lot_info.get("landUse")
                        prop_type = _classify_property_type(use_code, land_use)

                        # Filter by requested property types
                        if property_types and prop_type not in property_types:
                            continue

                        # Calculate opportunity signals
                        signals, opp_score = _calculate_opportunity_signals(prop)

                        # Filter by minimum opportunity score
                        if opp_score < min_opportunity_score:
                            continue

                        # Build address string
                        street = address_info.get("line1", "")
                        city = address_info.get("locality", "")
                        state = address_info.get("countrySubd", "")
                        zip_code = address_info.get("postal1", "")

                        full_address = street or f"{lat:.4f}, {lng:.4f}"

                        # Get pricing info
                        assessed_value = assessment_info.get("assessed", {}).get("assdTtlValue")
                        market_value = prop.get("avm", {}).get("amount", {}).get("value")
                        last_sale_price = sale_info.get("saleTransAmount")

                        # Use market value or assessed value as estimated price
                        price = market_value or assessed_value

                        # Get building info
                        sqft = building_info.get("size", {}).get("grossSize")
                        year_built = building_info.get("construction", {}).get("yearBuilt")
                        lot_acres = lot_info.get("lotSize1")

                        # Get owner info
                        owner_name = assessment_info.get("owner", {}).get("owner1", {}).get("fullName")
                        owner_type = assessment_info.get("ownerType")

                        listing = PropertyListing(
                            id=f"attom_{prop.get('identifier', {}).get('attomId', hash(f'{lat}{lng}'))}",
                            address=full_address,
                            city=city,
                            state=state,
                            zip_code=zip_code,
                            latitude=float(lat),
                            longitude=float(lng),
                            property_type=prop_type,
                            price=price,
                            price_display=_format_price(price),
                            sqft=float(sqft) if sqft else None,
                            lot_size_acres=float(lot_acres) if lot_acres else None,
                            year_built=int(year_built) if year_built else None,
                            owner_name=owner_name,
                            owner_type=owner_type,
                            assessed_value=float(assessed_value) if assessed_value else None,
                            market_value=float(market_value) if market_value else None,
                            last_sale_date=sale_info.get("saleTransDate"),
                            last_sale_price=float(last_sale_price) if last_sale_price else None,
                            source=PropertySource.ATTOM,
                            listing_type="opportunity",  # ATTOM provides opportunity data, not active listings
                            opportunity_signals=signals,
                            opportunity_score=opp_score,
                            raw_data=prop if settings.DEBUG else None,
                        )

                        properties.append(listing)

                    except Exception as e:
                        print(f"[ATTOM] Error parsing property: {e}")
                        continue

            elif response.status_code == 401:
                raise ValueError("ATTOM API authentication failed - check your API key")
            elif response.status_code == 429:
                raise ValueError("ATTOM API rate limit exceeded - try again later")
            else:
                print(f"[ATTOM] API returned status {response.status_code}: {response.text[:500]}")

        except httpx.RequestError as e:
            print(f"[ATTOM] Request error: {e}")
            raise ValueError(f"Failed to connect to ATTOM API: {e}")

    # Sort by opportunity score (highest first)
    properties.sort(key=lambda p: p.opportunity_score or 0, reverse=True)

    return PropertySearchResult(
        center_latitude=center_lat,
        center_longitude=center_lng,
        radius_miles=approx_radius,
        properties=properties,
        total_found=len(properties),
        sources=["ATTOM"],
        search_timestamp=datetime.now().isoformat(),
    )


async def search_properties_by_radius(
    latitude: float,
    longitude: float,
    radius_miles: float = 5.0,
    property_types: Optional[List[PropertyType]] = None,
    min_opportunity_score: float = 0,
    limit: int = 50,
) -> PropertySearchResult:
    """
    Search for properties within a radius of a point.

    Converts radius to bounds and calls search_properties_by_bounds.
    """
    # Convert radius to approximate bounds
    # 1 degree latitude ≈ 69 miles
    # 1 degree longitude ≈ 69 miles * cos(latitude)
    import math

    lat_delta = radius_miles / 69
    lng_delta = radius_miles / (69 * math.cos(math.radians(latitude)))

    bounds = GeoBounds(
        min_lat=latitude - lat_delta,
        max_lat=latitude + lat_delta,
        min_lng=longitude - lng_delta,
        max_lng=longitude + lng_delta,
    )

    result = await search_properties_by_bounds(
        bounds=bounds,
        property_types=property_types,
        min_opportunity_score=min_opportunity_score,
        limit=limit,
    )

    # Update with actual center and radius
    result.center_latitude = latitude
    result.center_longitude = longitude
    result.radius_miles = radius_miles

    return result


async def get_property_details(attom_id: str) -> Optional[PropertyListing]:
    """
    Get detailed information for a specific property by ATTOM ID.

    Fetches comprehensive property data including:
    - Full assessment details
    - Complete sale history
    - Building characteristics
    - AVM (Automated Valuation Model) estimate
    """
    if not settings.ATTOM_API_KEY:
        raise ValueError("ATTOM_API_KEY not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{ATTOM_BASE_URL}/property/detail",
                headers=_get_headers(),
                params={"attomId": attom_id},
            )

            if response.status_code == 200:
                data = response.json()
                prop = data.get("property", [{}])[0]

                # Similar parsing logic as search...
                # (Implementation would mirror the search parsing)

                return None  # TODO: Implement full detail parsing

            else:
                print(f"[ATTOM] Detail API returned {response.status_code}")
                return None

        except Exception as e:
            print(f"[ATTOM] Error fetching property details: {e}")
            return None


async def check_attom_api_key() -> dict:
    """
    Verify ATTOM API key is valid by making a test request.
    """
    if not settings.ATTOM_API_KEY:
        return {
            "configured": False,
            "valid": False,
            "message": "ATTOM_API_KEY not configured",
        }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Make a minimal test request
            response = await client.get(
                f"{ATTOM_BASE_URL}/property/snapshot",
                headers=_get_headers(),
                params={
                    "address1": "123 Main St",
                    "address2": "New York, NY",
                },
            )

            if response.status_code == 200:
                return {
                    "configured": True,
                    "valid": True,
                    "message": "ATTOM API key is valid",
                }
            elif response.status_code == 401:
                return {
                    "configured": True,
                    "valid": False,
                    "message": "ATTOM API key is invalid or expired",
                }
            else:
                return {
                    "configured": True,
                    "valid": True,  # Other errors don't mean key is invalid
                    "message": f"ATTOM API returned status {response.status_code}",
                }

        except Exception as e:
            return {
                "configured": True,
                "valid": False,
                "message": f"Failed to verify ATTOM API key: {e}",
            }
