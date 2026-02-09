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

    # Land use classification from ATTOM (e.g., "Gas Station/Mini Mart", "Retail Store (NEC)")
    land_use: Optional[str] = None

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


def _classify_property_type(
    prop_indicator: Optional[str] = None,
    prop_type: Optional[str] = None,
    land_use: Optional[str] = None
) -> PropertyType:
    """
    Classify property type based on ATTOM property indicator or text descriptions.

    ATTOM Property Indicators:
    - 20 = Commercial (general)
    - 25 = Retail
    - 27 = Office Building
    - 50 = Industrial
    - 51 = Industrial Light
    - 52 = Industrial Heavy
    - 80 = Vacant Land
    """
    # First try property indicator (most reliable)
    if prop_indicator:
        indicator = str(prop_indicator)
        if indicator == "25":
            return PropertyType.RETAIL
        elif indicator == "27":
            return PropertyType.OFFICE
        elif indicator in ("50", "51", "52"):
            return PropertyType.INDUSTRIAL
        elif indicator == "80":
            return PropertyType.LAND
        elif indicator == "20":
            # Generic commercial - check text for more specific classification
            pass

    # Fall back to text-based classification
    combined = f"{prop_type or ''} {land_use or ''}".lower()

    if not combined.strip():
        return PropertyType.UNKNOWN

    # Office indicators
    if any(x in combined for x in ["office", "professional"]):
        return PropertyType.OFFICE

    # Retail indicators
    if any(x in combined for x in ["retail", "store", "shop", "restaurant"]):
        return PropertyType.RETAIL

    # Industrial indicators
    if any(x in combined for x in ["industrial", "warehouse", "manufacturing", "distribution"]):
        return PropertyType.INDUSTRIAL

    # Land indicators
    if any(x in combined for x in ["vacant", "land", "lot", "undeveloped", "acreage"]):
        return PropertyType.LAND

    # Mixed use indicators
    if any(x in combined for x in ["mixed", "multi-use", "residential"]):
        return PropertyType.MIXED_USE

    # Default commercial
    if "commercial" in combined:
        return PropertyType.RETAIL

    return PropertyType.UNKNOWN


def _calculate_opportunity_signals(property_data: dict) -> tuple[List[OpportunitySignal], float]:
    """
    Calculate opportunity signals and score based on property data.

    Returns (signals_list, opportunity_score)
    """
    signals = []
    score = 0.0

    # Debug: Log available data fields to understand what ATTOM returns
    summary = property_data.get("summary", {})
    assessment = property_data.get("assessment", {})
    sale = property_data.get("sale", {})
    lot = property_data.get("lot", {})
    avm = property_data.get("avm", {})

    print(f"[ATTOM Signal Debug] Available data: summary={bool(summary)}, assessment={bool(assessment)}, sale={bool(sale)}, lot={bool(lot)}, avm={bool(avm)}")

    # ========== HIGH-VALUE SIGNALS ==========

    # Check for tax delinquency
    tax_delinquent = assessment.get("taxDelinquent")
    if tax_delinquent:
        signals.append(OpportunitySignal(
            signal_type="tax_delinquent",
            description="Property has delinquent taxes",
            strength="high"
        ))
        score += 25

    # Check for foreclosure/pre-foreclosure status
    foreclosure_status = sale.get("foreclosureStatus")
    if foreclosure_status:
        signals.append(OpportunitySignal(
            signal_type="distress",
            description=f"Foreclosure status: {foreclosure_status}",
            strength="high"
        ))
        score += 30

    # ========== MEDIUM-VALUE SIGNALS ==========

    # Check ownership duration (long-term owners more likely to sell)
    last_sale = sale.get("saleTransDate")
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
            elif years_owned > 10:
                signals.append(OpportunitySignal(
                    signal_type="established_owner",
                    description=f"Owned for {int(years_owned)} years",
                    strength="low"
                ))
                score += 5
        except (ValueError, TypeError):
            pass

    # Check for corporate vs individual ownership (estates, trusts = opportunity)
    owner_type = assessment.get("ownerType", "").lower()
    if "trust" in owner_type or "estate" in owner_type:
        signals.append(OpportunitySignal(
            signal_type="estate_ownership",
            description="Owned by trust or estate",
            strength="medium"
        ))
        score += 20

    # Check assessed vs market value gap
    assessed_value = assessment.get("assessed", {}).get("assdTtlValue") or assessment.get("assessedValue")
    market_value = avm.get("amount", {}).get("value")

    if assessed_value and market_value and market_value > 0:
        ratio = assessed_value / market_value
        if ratio < 0.7:  # Assessed at less than 70% of market (undervalued)
            signals.append(OpportunitySignal(
                signal_type="undervalued",
                description=f"Assessed {int(ratio*100)}% below market value",
                strength="medium"
            ))
            score += 10
        elif ratio > 1.2:  # Assessed significantly above market (overassessed = motivated seller)
            signals.append(OpportunitySignal(
                signal_type="overassessed",
                description="Assessed value exceeds market estimate",
                strength="low"
            ))
            score += 5

    # Large lot opportunity (more development potential)
    lot_sqft = lot.get("lotSize1") or lot.get("lotsize1")
    if lot_sqft:
        lot_acres = float(lot_sqft) / 43560
        if lot_acres >= 2.0:
            signals.append(OpportunitySignal(
                signal_type="large_lot",
                description=f"Large lot: {lot_acres:.2f} acres",
                strength="medium"
            ))
            score += 10
        elif lot_acres >= 1.0:
            signals.append(OpportunitySignal(
                signal_type="sizeable_lot",
                description=f"Lot size: {lot_acres:.2f} acres",
                strength="low"
            ))
            score += 5

    # ========== NEW ENHANCED SIGNALS (Added Feb 4, 2026) ==========

    # Check building age (older buildings = renovation/redevelopment opportunity)
    building = property_data.get("building", {})
    year_built = building.get("yearBuilt") or summary.get("yearBuilt")
    if year_built:
        try:
            building_age = datetime.now().year - int(year_built)
            if building_age >= 50:
                signals.append(OpportunitySignal(
                    signal_type="aging_building",
                    description=f"Built {year_built} ({building_age} years old) - renovation opportunity",
                    strength="medium"
                ))
                score += 15
            elif building_age >= 30:
                signals.append(OpportunitySignal(
                    signal_type="mature_building",
                    description=f"Built {year_built} - potential for updates",
                    strength="low"
                ))
                score += 5
        except (ValueError, TypeError):
            pass

    # Check for absentee owner (out-of-state = less attachment, higher likelihood to sell)
    owner_address = assessment.get("owner", {})
    owner_state = owner_address.get("state") if isinstance(owner_address, dict) else None
    property_state = summary.get("state") or property_data.get("address", {}).get("state")
    
    if owner_state and property_state and owner_state.upper() != property_state.upper():
        signals.append(OpportunitySignal(
            signal_type="absentee_owner",
            description=f"Out-of-state owner ({owner_state})",
            strength="medium"
        ))
        score += 12

    # Check for recent tax increases (financial pressure indicator)
    tax_assessment = assessment.get("assessed", {})
    prior_value = tax_assessment.get("assdPriorYearValue")
    current_value = tax_assessment.get("assdTtlValue") or assessment.get("assessedValue")
    
    if prior_value and current_value and prior_value > 0:
        tax_increase_pct = ((current_value - prior_value) / prior_value) * 100
        if tax_increase_pct > 20:  # More than 20% increase
            signals.append(OpportunitySignal(
                signal_type="tax_pressure",
                description=f"Tax assessment increased {tax_increase_pct:.0f}% recently",
                strength="medium"
            ))
            score += 12
        elif tax_increase_pct > 10:  # 10-20% increase
            signals.append(OpportunitySignal(
                signal_type="rising_taxes",
                description=f"Tax assessment up {tax_increase_pct:.0f}%",
                strength="low"
            ))
            score += 5

    # Check for vacant/unoccupied status
    occupancy = building.get("occupancyStatus") or summary.get("occupancyStatus")
    if occupancy and "vacant" in str(occupancy).lower():
        signals.append(OpportunitySignal(
            signal_type="vacant_property",
            description="Property appears vacant",
            strength="high"
        ))
        score += 20

    # Multiple parcels indicator (from lot info)
    parcel_count = lot.get("parcelCount")
    if parcel_count and int(parcel_count) > 1:
        signals.append(OpportunitySignal(
            signal_type="multiple_parcels",
            description=f"{parcel_count} parcels - assemblage opportunity",
            strength="medium"
        ))
        score += 10

    # ========== FALLBACK SIGNALS (ensure something always shows) ==========

    # Property type indicator as baseline signal
    prop_type = summary.get("proptype") or summary.get("propertyType") or ""
    prop_indicator = summary.get("propIndicator")

    if not signals:  # Only add fallback if no other signals
        # Commercial property indicator with better descriptions
        if prop_indicator in ("20", "25", "27", "50", "80"):
            type_descriptions = {
                "20": "Commercial property - general use",
                "25": "Retail-zoned property - high visibility location",
                "27": "Office building - professional space opportunity",
                "50": "Industrial property - warehouse/manufacturing potential",
                "80": "Vacant land - development opportunity"
            }
            signals.append(OpportunitySignal(
                signal_type="commercial_zoning",
                description=type_descriptions.get(prop_indicator, "Commercial property"),
                strength="low"
            ))
            score += 8

        # If still no signals, add context-aware opportunity indicator
        if not signals:
            if lot_sqft and float(lot_sqft) > 21780:  # More than 0.5 acres
                signals.append(OpportunitySignal(
                    signal_type="land_opportunity",
                    description="Sizeable commercial parcel in your search area",
                    strength="low"
                ))
                score += 10
            elif assessed_value or market_value:
                value = market_value or assessed_value
                if value and value < 500_000:
                    signals.append(OpportunitySignal(
                        signal_type="entry_level",
                        description="Entry-level commercial property - lower barrier to entry",
                        strength="low"
                    ))
                    score += 8
                else:
                    signals.append(OpportunitySignal(
                        signal_type="market_listing",
                        description="Commercial property in target market",
                        strength="low"
                    ))
                    score += 5

    # Cap score at 100
    score = min(score, 100)

    # Ensure minimum score if we have signals
    if signals and score < 5:
        score = 5

    print(f"[ATTOM Signal Debug] Generated {len(signals)} signals with score {score}")

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

    Converts bounds to center point + radius and calls search_properties_by_radius.
    """
    import math

    # Calculate center point
    center_lat = (bounds.min_lat + bounds.max_lat) / 2
    center_lng = (bounds.min_lng + bounds.max_lng) / 2

    # Calculate approximate radius in miles (use the larger dimension)
    lat_diff = bounds.max_lat - bounds.min_lat
    lng_diff = bounds.max_lng - bounds.min_lng
    # 1 degree latitude ≈ 69 miles, longitude varies by latitude
    lat_miles = lat_diff * 69
    lng_miles = lng_diff * 69 * math.cos(math.radians(center_lat))
    approx_radius = max(lat_miles, lng_miles) / 2

    # Cap radius at ATTOM's max of 20 miles
    approx_radius = min(approx_radius, 20.0)

    # Delegate to radius-based search
    return await search_properties_by_radius(
        latitude=center_lat,
        longitude=center_lng,
        radius_miles=approx_radius,
        property_types=property_types,
        min_opportunity_score=min_opportunity_score,
        limit=limit,
    )


# Property indicator mapping for ATTOM API
# See: https://cloud-help.attomdata.com/article/688-property-indicator
ATTOM_PROPERTY_INDICATORS = {
    PropertyType.RETAIL: "25",
    PropertyType.OFFICE: "27",
    PropertyType.INDUSTRIAL: "50",
    PropertyType.LAND: "80",
    PropertyType.MIXED_USE: "20",  # General commercial
    PropertyType.UNKNOWN: "20",
}


async def _search_attom_api(
    latitude: float,
    longitude: float,
    radius_miles: float,
    property_types: Optional[List[PropertyType]] = None,
    min_opportunity_score: float = 0,
    limit: int = 50,
) -> PropertySearchResult:
    """
    Core ATTOM API search using correct parameters.

    Uses latitude/longitude/radius instead of bounding box.
    Uses propertyindicator instead of propertytype.
    """
    if not settings.ATTOM_API_KEY:
        raise ValueError("ATTOM_API_KEY not configured")

    # Build property indicator filter
    # Default: all commercial types (20=Commercial, 25=Retail, 27=Office, 50=Industrial, 80=Vacant)
    if property_types:
        indicators = [ATTOM_PROPERTY_INDICATORS.get(pt, "20") for pt in property_types]
        property_indicator = "|".join(set(indicators))
    else:
        property_indicator = "20|25|27|50|80"  # All commercial types

    # Cap radius at ATTOM's max of 20 miles
    radius_miles = min(radius_miles, 20.0)

    properties = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # ATTOM Property Search using correct parameters
            # Per docs: https://api.developer.attomdata.com/docs
            response = await client.get(
                f"{ATTOM_BASE_URL}/property/snapshot",
                headers=_get_headers(),
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": radius_miles,
                    "propertyindicator": property_indicator,
                    "pagesize": min(limit, 100),  # ATTOM max is 100
                },
            )

            print(f"[ATTOM] API request: lat={latitude}, lng={longitude}, radius={radius_miles}, indicators={property_indicator}")

            if response.status_code == 200:
                data = response.json()
                property_list = data.get("property", [])
                print(f"[ATTOM] Found {len(property_list)} properties in response")

                for prop in property_list:
                    try:
                        # Extract data sections
                        address_info = prop.get("address", {})
                        location_info = prop.get("location", {})
                        summary_info = prop.get("summary", {})  # Key info is here!
                        assessment_info = prop.get("assessment", {})
                        sale_info = prop.get("sale", {})
                        building_info = prop.get("building", {})
                        lot_info = prop.get("lot", {})

                        # Get coordinates
                        lat = location_info.get("latitude")
                        lng = location_info.get("longitude")

                        if not lat or not lng:
                            continue

                        # Classify property type using summary data
                        prop_indicator = summary_info.get("propIndicator")
                        prop_type_text = summary_info.get("propertyType") or summary_info.get("proptype")
                        land_use = summary_info.get("propLandUse")
                        prop_type = _classify_property_type(prop_indicator, prop_type_text, land_use)

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

                        # Get building info - check both locations
                        sqft = building_info.get("size", {}).get("universalsize") or building_info.get("size", {}).get("grossSize")
                        year_built = summary_info.get("yearbuilt") or building_info.get("construction", {}).get("yearBuilt")
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
                            land_use=land_use,
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
        center_latitude=latitude,
        center_longitude=longitude,
        radius_miles=radius_miles,
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

    Uses ATTOM's radius-based search API directly.
    """
    return await _search_attom_api(
        latitude=latitude,
        longitude=longitude,
        radius_miles=radius_miles,
        property_types=property_types,
        min_opportunity_score=min_opportunity_score,
        limit=limit,
    )


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
