"""
Opportunities API - ATTOM-based property opportunity filtering for CSOKi.

Filters properties based on:
- Parcel size: 0.8-2 acres
- Building size: 2500-6000 sqft (if building exists)
- Property types: Retail preferred, office acceptable
- Focus: Empty parcels OR vacant single-tenant buildings
- Exclude: Multi-tenant buildings
- Proximity: Must be within 1 mile of a Verizon-family store
  (Russell Cellular, Victra, Verizon Corporate)

Opportunity Signals (Priority Order):
1. Empty parcels (land only)
2. Vacant properties
3. Out-of-state/absentee owners
4. Tax liens/pressure
5. Aging owners (65+)
6. Small single-tenant buildings

Market Viability Scoring (additive):
- Verizon Corporate store distance (3-5mi gap preferred)
- Population threshold (12K+ within 1-3mi radius)
- Major retail node proximity (within 0.5mi of anchors)
"""

import asyncio
import logging
import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.attom import (
    search_properties_by_bounds as attom_search_bounds,
    PropertySearchResult,
    PropertyListing,
    GeoBounds,
    PropertyType,
    PropertySource,
    OpportunitySignal,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.store import Store
from app.models.scraped_listing import ScrapedListing
from app.utils.geo import haversine
from app.services.viewport_cache import (
    get_cached_demographics,
    cache_demographics,
    get_cached_retail_nodes,
    cache_retail_nodes,
)
from app.services.arcgis import fetch_demographics
from app.services.mapbox_places import fetch_mapbox_pois

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

# Verizon-family brands that CSOKi opportunities must be distant from
VERIZON_FAMILY_BRANDS = ["russell_cellular", "victra", "verizon_corporate"]

# Land use keywords indicating incompatible commercial uses (can't convert to wireless retail)
EXCLUDED_LAND_USE_KEYWORDS = {
    # Gas/Auto
    "gas station", "service station", "auto repair", "car wash", "tire",
    "oil change", "auto body", "auto dealer", "parking garage", "parking lot",
    "auto parts", "auto service",
    # Food/Drink
    "restaurant", "fast food", "bar ", "tavern", "brewery", "pizza",
    "coffee shop", "bakery", "deli", "liquor store", "ice cream", "donut",
    # Medical
    "dental", "medical", "hospital", "clinic", "veterinar", "pharmacy",
    "optom", "chiropract", "urgent care", "dialysis", "physician",
    # Finance
    "bank", "credit union",
    # Lodging
    "hotel", "motel", "inn ", "resort",
    # Religious/Civic
    "church", "mosque", "temple", "synagogue", "worship", "funeral",
    "cemetery", "mortuary", "cremator",
    # Industrial/Utility
    "warehouse", "storage", "industrial", "manufacturing", "plant ",
    "utility", "water treatment",
    # Government
    "government", "post office", "fire station", "police", "library",
    "courthouse",
    # Education
    "school", "university", "college", "daycare", "child care",
    # Other incompatible
    "laundromat", "dry clean", "salon", "barber", "tattoo", "nail salon",
    "gym", "fitness", "bowling", "theater", "cinema", "nightclub",
    "car dealer", "grocery", "supermarket", "convenience store",
}

# Land use keywords indicating the property IS available (bypass occupied-building check)
AVAILABILITY_LAND_USE_KEYWORDS = {
    "vacant", "former", "closed", "abandoned", "demolished", "unused",
}

# Land use keywords indicating a desirable format (scoring bonus only, NOT availability evidence)
DESIRABLE_FORMAT_KEYWORDS = {
    "retail store", "commercial", "general retail", "strip", "shopping",
    "storefront", "office building", "professional office", "mixed use",
}


def _is_excluded_land_use(land_use: str | None) -> bool:
    """Check if a property's land use indicates an incompatible commercial use."""
    if not land_use:
        return False
    land_use_lower = land_use.lower()
    return any(keyword in land_use_lower for keyword in EXCLUDED_LAND_USE_KEYWORDS)


def _has_availability_keywords(land_use: str | None) -> bool:
    """Check if land use text indicates the property is available (vacant, former, closed, etc.)."""
    if not land_use:
        return False
    land_use_lower = land_use.lower()
    return any(keyword in land_use_lower for keyword in AVAILABILITY_LAND_USE_KEYWORDS)


def _is_desirable_format(land_use: str | None) -> bool:
    """Check if land use indicates a desirable building format for Verizon retail."""
    if not land_use:
        return False
    land_use_lower = land_use.lower()
    return any(keyword in land_use_lower for keyword in DESIRABLE_FORMAT_KEYWORDS)


def _fetch_scraped_listings(
    db: Session,
    bounds: GeoBounds,
    min_parcel_acres: float,
    max_parcel_acres: float,
    min_building_sqft: Optional[float],
    max_building_sqft: Optional[float],
    include_retail: bool,
    include_office: bool,
    include_land: bool,
) -> List[PropertyListing]:
    """
    Fetch active scraped listings (Crexi/LoopNet) within map bounds
    and convert them to PropertyListing objects for the opportunity pipeline.
    """
    query = db.query(ScrapedListing).filter(
        ScrapedListing.is_active == True,
        ScrapedListing.latitude.isnot(None),
        ScrapedListing.longitude.isnot(None),
        ScrapedListing.latitude >= bounds.min_lat,
        ScrapedListing.latitude <= bounds.max_lat,
        ScrapedListing.longitude >= bounds.min_lng,
        ScrapedListing.longitude <= bounds.max_lng,
    )

    # Property type filter
    allowed_types = []
    if include_retail:
        allowed_types.append("retail")
    if include_office:
        allowed_types.append("office")
    if include_land:
        allowed_types.append("land")
    if allowed_types:
        query = query.filter(ScrapedListing.property_type.in_(allowed_types))

    rows = query.limit(200).all()
    properties = []

    # Map source string to PropertySource enum
    source_map = {"crexi": PropertySource.CREXI, "loopnet": PropertySource.LOOPNET}
    # Map property_type string to PropertyType enum
    type_map = {
        "retail": PropertyType.RETAIL,
        "office": PropertyType.OFFICE,
        "land": PropertyType.LAND,
        "industrial": PropertyType.INDUSTRIAL,
        "mixed_use": PropertyType.MIXED_USE,
    }

    for row in rows:
        # Apply size filters (lot size only applies to land — buildings are sqft-filtered)
        if row.lot_size_acres and row.property_type == "land":
            if row.lot_size_acres < min_parcel_acres or row.lot_size_acres > max_parcel_acres:
                continue
        if row.sqft and row.property_type != "land":
            if min_building_sqft and row.sqft < min_building_sqft:
                continue
            if max_building_sqft and row.sqft > max_building_sqft:
                continue

        source = source_map.get(row.source, PropertySource.CREXI)
        # Default to RETAIL for scraped listings (from commercial listing sites)
        prop_type = type_map.get(row.property_type, PropertyType.RETAIL if row.property_type else PropertyType.UNKNOWN)
        source_label = row.source.title() if row.source else "Listing"

        listing = PropertyListing(
            id=f"scraped-{row.id}",
            address=row.address or f"{row.city}, {row.state}",
            city=row.city,
            state=row.state,
            zip_code=row.postal_code,
            latitude=row.latitude,
            longitude=row.longitude,
            property_type=prop_type,
            price=row.price,
            price_display=row.price_display,
            sqft=row.sqft,
            lot_size_acres=row.lot_size_acres,
            year_built=row.year_built,
            source=source,
            listing_type="active_listing",
            opportunity_signals=[
                OpportunitySignal(
                    signal_type="active_listing",
                    description=f"Actively listed for lease/sale on {source_label}",
                    strength="high",
                )
            ],
            opportunity_score=80.0,
            listing_url=row.listing_url,
            broker_name=row.broker_name,
            broker_company=row.broker_company,
            listing_images=row.images if isinstance(row.images, list) else None,
        )
        properties.append(listing)

    logger.info(f"Fetched {len(properties)} scraped listings within bounds")
    return properties


def _merge_and_deduplicate(
    attom_properties: List[PropertyListing],
    scraped_properties: List[PropertyListing],
) -> List[PropertyListing]:
    """
    Merge ATTOM and scraped properties, deduplicating by proximity.
    If a scraped listing is within ~50m of an ATTOM property, keep the scraped version.
    """
    if not scraped_properties:
        return attom_properties

    # Build set of scraped locations for quick proximity check
    scraped_coords = [(p.latitude, p.longitude) for p in scraped_properties]

    deduplicated_attom = []
    for prop in attom_properties:
        is_duplicate = False
        for slat, slng in scraped_coords:
            if abs(prop.latitude - slat) < 0.0005 and abs(prop.longitude - slng) < 0.0005:
                is_duplicate = True
                break
        if not is_duplicate:
            deduplicated_attom.append(prop)

    removed = len(attom_properties) - len(deduplicated_attom)
    if removed > 0:
        logger.info(f"Dedup: removed {removed} ATTOM properties overlapping with scraped listings")

    return scraped_properties + deduplicated_attom


def _filter_by_verizon_family_proximity(
    properties: List[PropertyListing],
    db: Session,
    bounds_min_lat: float,
    bounds_max_lat: float,
    bounds_min_lng: float,
    bounds_max_lng: float,
    max_distance_miles: float,
) -> List[PropertyListing]:
    """
    Keep only properties that are within max_distance_miles of at least one
    Russell Cellular, Victra, or Verizon Corporate store.
    """
    if max_distance_miles <= 0:
        return properties

    # Expand search bounds by ~max_distance_miles to catch stores just outside viewport
    # 1 degree latitude ≈ 69 miles
    lat_buffer = max_distance_miles / 69.0
    lng_buffer = max_distance_miles / 55.0  # Conservative estimate for mid-US latitudes

    verizon_stores = db.query(Store).filter(
        Store.brand.in_(VERIZON_FAMILY_BRANDS),
        Store.latitude.isnot(None),
        Store.longitude.isnot(None),
        Store.latitude >= bounds_min_lat - lat_buffer,
        Store.latitude <= bounds_max_lat + lat_buffer,
        Store.longitude >= bounds_min_lng - lng_buffer,
        Store.longitude <= bounds_max_lng + lng_buffer,
    ).all()

    if len(verizon_stores) <= 3:
        logger.info(f"Sparse VZ market ({len(verizon_stores)} stores in viewport) — skipping proximity filter")
        return properties

    filtered = []
    for prop in properties:
        if prop.latitude is None or prop.longitude is None:
            continue
        for store in verizon_stores:
            dist = haversine(prop.longitude, prop.latitude, store.longitude, store.latitude)
            if dist <= max_distance_miles:
                filtered.append(prop)
                break

    return filtered


class OpportunitySearchRequest(BaseModel):
    """Request for opportunity search with CSOKi-specific filters."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float
    
    # Optional overrides for parcel/building size
    min_parcel_acres: float = Field(default=0.8, description="Minimum parcel size in acres")
    max_parcel_acres: float = Field(default=2.0, description="Maximum parcel size in acres")
    min_building_sqft: Optional[float] = Field(default=2500, description="Minimum building size (if building exists)")
    max_building_sqft: Optional[float] = Field(default=6000, description="Maximum building size (if building exists)")
    
    # Property type preferences
    include_retail: bool = Field(default=True, description="Include retail properties")
    include_office: bool = Field(default=True, description="Include office properties")
    include_land: bool = Field(default=True, description="Include empty parcels")
    
    # Opportunity signal filtering
    require_opportunity_signal: bool = Field(default=True, description="Only return properties with opportunity signals")
    min_opportunity_score: float = Field(default=0, description="Minimum opportunity score (0-100)")

    # Proximity filter: must be within this distance of a Verizon-family store
    max_verizon_family_distance: float = Field(
        default=1.0,
        ge=0,
        le=10,
        description="Max distance (miles) to nearest Russell Cellular, Victra, or Verizon Corporate store"
    )

    # Market viability scoring toggles
    enable_corporate_distance_scoring: bool = Field(
        default=True,
        description="Score based on distance from Verizon Corporate stores (farther = better)"
    )
    enable_population_scoring: bool = Field(
        default=True,
        description="Score based on population density (12K+ within 1-3mi)"
    )
    enable_retail_node_scoring: bool = Field(
        default=True,
        description="Score based on proximity to major retail anchors (within 0.5mi)"
    )

    limit: int = Field(default=100, le=500, description="Maximum results to return")


class OpportunityRanking(BaseModel):
    """Enhanced opportunity metadata with ranking."""
    property: PropertyListing
    rank: int  # 1-based ranking (1 = highest priority)
    priority_signals: List[str]  # Which high-priority signals are present
    signal_count: int  # Total number of signals

    # Market viability enrichment
    nearest_corporate_store_miles: Optional[float] = None
    nearest_retail_node_miles: Optional[float] = None
    nearest_retail_node_name: Optional[str] = None
    area_population_1mi: Optional[int] = None
    area_population_3mi: Optional[int] = None
    market_viability_score: Optional[float] = None


class OpportunitySearchResponse(BaseModel):
    """Response for opportunity search."""
    center_latitude: float
    center_longitude: float
    total_found: int
    opportunities: List[OpportunityRanking]
    search_timestamp: str
    filters_applied: dict

    # Market viability metadata
    corporate_stores_in_area: int = 0
    retail_nodes_found: int = 0
    viewport_population_center: Optional[dict] = None


def _calculate_corporate_store_distances(
    properties: List[PropertyListing],
    db: Session,
    bounds_min_lat: float,
    bounds_max_lat: float,
    bounds_min_lng: float,
    bounds_max_lng: float,
) -> tuple[dict[str, float], int]:
    """
    Calculate distance from each property to the nearest Verizon Corporate store.

    Returns:
        (distance_map, store_count) where distance_map is {property_id: miles}
    """
    # Search with a generous buffer to catch corporate stores just outside viewport
    buffer_miles = 10.0
    lat_buffer = buffer_miles / 69.0
    lng_buffer = buffer_miles / 55.0

    corporate_stores = db.query(Store).filter(
        Store.brand == "verizon_corporate",
        Store.latitude.isnot(None),
        Store.longitude.isnot(None),
        Store.latitude >= bounds_min_lat - lat_buffer,
        Store.latitude <= bounds_max_lat + lat_buffer,
        Store.longitude >= bounds_min_lng - lng_buffer,
        Store.longitude <= bounds_max_lng + lng_buffer,
    ).all()

    distance_map: dict[str, float] = {}
    for prop in properties:
        if prop.latitude is None or prop.longitude is None:
            continue
        if not corporate_stores:
            # No corporate stores nearby - maximum gap
            distance_map[prop.id] = 999.0
            continue
        min_dist = min(
            haversine(prop.longitude, prop.latitude, store.longitude, store.latitude)
            for store in corporate_stores
        )
        distance_map[prop.id] = round(min_dist, 2)

    return distance_map, len(corporate_stores)


def _calculate_priority_rank(
    listing: PropertyListing,
    nearest_corporate_distance: Optional[float] = None,
    nearest_retail_node_distance: Optional[float] = None,
    area_population_1mi: Optional[int] = None,
    area_population_3mi: Optional[int] = None,
) -> tuple[int, List[str]]:
    """
    Calculate priority rank based on opportunity signals and market viability.

    Returns (rank_score, priority_signals)
    Higher rank_score = higher priority

    Property Signals:
    1. Empty parcels (land only) - 100 points
    2. Vacant properties - 80 points
    3. Out-of-state/absentee owners - 60 points
    4. Tax liens/pressure - 50 points
    5. Aging owners (65+) - 40 points
    6. Small single-tenant buildings - 25-40 points (land-use aware)
    7. Vacancy boost for buildings - 10-20 points
    Note: Occupied buildings are hard-filtered before scoring.

    Market Viability (additive):
    - Corporate store gap: up to +20 points
    - Population density: up to +25 points
    - Retail node proximity: up to +25 points
    """
    rank_score = 0
    priority_signals = []

    signal_types = {s.signal_type for s in listing.opportunity_signals}

    # 0. Active listing bonus — confirmed for-lease is the best possible signal
    if listing.source in (PropertySource.CREXI, PropertySource.LOOPNET):
        rank_score += 120
        source_label = listing.source.value.title()
        priority_signals.append(f"Active listing ({source_label})")

    # 1. Empty parcels (land only)
    if listing.property_type == PropertyType.LAND:
        rank_score += 100
        priority_signals.append("Empty parcel (land only)")

    # 2. Vacant properties
    if "vacant_property" in signal_types:
        rank_score += 80
        priority_signals.append("Vacant property")

    # 3. Out-of-state/absentee owners
    if "absentee_owner" in signal_types:
        rank_score += 60
        priority_signals.append("Out-of-state owner")

    # 4. Tax liens/pressure
    if "tax_delinquent" in signal_types:
        rank_score += 50
        priority_signals.append("Tax delinquent")
    elif "tax_pressure" in signal_types:
        rank_score += 40
        priority_signals.append("Tax pressure")

    # 5. Aging owners - check signal descriptions for age mentions
    for signal in listing.opportunity_signals:
        if "estate" in signal.signal_type or "trust" in signal.signal_type:
            rank_score += 40
            priority_signals.append("Estate/trust ownership")
            break

    # 6. Small single-tenant buildings (format-aware scoring)
    if listing.property_type in (PropertyType.RETAIL, PropertyType.OFFICE):
        if listing.sqft and 2500 <= listing.sqft <= 6000:
            if _has_availability_keywords(listing.land_use):
                rank_score += 40
                priority_signals.append("Ideal small building (vacant/available)")
            elif _is_desirable_format(listing.land_use):
                rank_score += 30
                priority_signals.append(f"Desirable format ({listing.land_use})")
            else:
                rank_score += 25
                priority_signals.append("Small single-tenant building")

    # 7. Vacancy boost for buildings
    if listing.property_type != PropertyType.LAND:
        has_vacancy = "vacant_property" in signal_types
        has_availability = _has_availability_keywords(listing.land_use)
        if has_vacancy and has_availability:
            rank_score += 20
            priority_signals.append(f"Confirmed vacant ({listing.land_use})")
        elif has_vacancy:
            rank_score += 15
            priority_signals.append("Confirmed vacant")

    # Bonus: Distressed properties (foreclosure, etc.)
    if "distress" in signal_types:
        rank_score += 70
        priority_signals.append("Foreclosure/distress")

    # --- Market Viability Scoring ---

    # Verizon Corporate store distance scoring
    if nearest_corporate_distance is not None:
        # Determine if this is a high-pop or low-pop market
        is_high_pop = (area_population_3mi or 0) >= 12000
        min_threshold = 3.0 if is_high_pop else 5.0

        if nearest_corporate_distance >= 7.0:
            rank_score += 20
            priority_signals.append(f"Excellent corporate gap ({nearest_corporate_distance:.1f}mi)")
        elif nearest_corporate_distance >= 5.0:
            rank_score += 15
            priority_signals.append(f"Strong corporate gap ({nearest_corporate_distance:.1f}mi)")
        elif nearest_corporate_distance >= min_threshold:
            rank_score += 10
            priority_signals.append(f"Adequate corporate gap ({nearest_corporate_distance:.1f}mi)")

    # Population density scoring
    if area_population_1mi is not None and area_population_1mi >= 12000:
        rank_score += 20
        priority_signals.append(f"Strong population density ({area_population_1mi:,} within 1mi)")
        if (area_population_3mi or 0) >= 25000:
            rank_score += 5
            priority_signals.append(f"High-density market ({area_population_3mi:,} within 3mi)")
    elif area_population_3mi is not None and area_population_3mi >= 12000:
        rank_score += 10
        priority_signals.append(f"Viable population ({area_population_3mi:,} within 3mi)")
        if area_population_3mi >= 25000:
            rank_score += 5
            priority_signals.append(f"High-density market ({area_population_3mi:,} within 3mi)")

    # Retail node proximity scoring
    if nearest_retail_node_distance is not None:
        if nearest_retail_node_distance <= 0.25:
            rank_score += 25
            priority_signals.append("Adjacent to major retail anchor")
        elif nearest_retail_node_distance <= 0.5:
            rank_score += 15
            priority_signals.append("Near major retail anchor (<0.5mi)")
        elif nearest_retail_node_distance <= 1.0:
            rank_score += 5
            priority_signals.append("Retail anchor within 1mi")

    return rank_score, priority_signals


def _filter_properties_for_opportunities(
    properties: List[PropertyListing],
    min_parcel_acres: float,
    max_parcel_acres: float,
    min_building_sqft: Optional[float],
    max_building_sqft: Optional[float],
    include_retail: bool,
    include_office: bool,
    include_land: bool,
    require_opportunity_signal: bool,
    min_opportunity_score: float,
) -> List[PropertyListing]:
    """Apply CSOKi-specific filters to property list."""
    filtered = []

    current_year = datetime.now().year

    for prop in properties:
        # Property type filter
        if prop.property_type == PropertyType.RETAIL and not include_retail:
            continue
        if prop.property_type == PropertyType.OFFICE and not include_office:
            continue
        if prop.property_type == PropertyType.LAND and not include_land:
            continue

        # Only retail, office, and land
        if prop.property_type not in (PropertyType.RETAIL, PropertyType.OFFICE, PropertyType.LAND):
            continue

        is_scraped = prop.source in (PropertySource.CREXI, PropertySource.LOOPNET)

        # Hard filter: incompatible land uses (gas stations, restaurants, medical, etc.)
        # Scraped listings bypass this (their land_use is None)
        if _is_excluded_land_use(prop.land_use):
            logger.debug(f"Filtered excluded land use: {prop.address} ({prop.land_use})")
            continue

        # Hard filter: occupied buildings are NOT opportunities.
        # Only empty parcels (LAND), buildings with vacancy/availability evidence,
        # and scraped listings (confirmed for-lease) pass through.
        if prop.property_type != PropertyType.LAND:
            if not is_scraped:
                prop_signal_types = {s.signal_type for s in prop.opportunity_signals}
                has_vacancy = "vacant_property" in prop_signal_types
                has_availability_keyword = _has_availability_keywords(prop.land_use)
                if not has_vacancy and not has_availability_keyword:
                    logger.debug(f"Filtered occupied building: {prop.address} ({prop.land_use})")
                    continue

        # Hard filter: established businesses (20+ year-old occupied buildings)
        # Must have vacancy, distress, or availability evidence to pass
        if prop.property_type != PropertyType.LAND and not is_scraped:
            if prop.year_built and (current_year - prop.year_built) > 20:
                prop_signal_types = {s.signal_type for s in prop.opportunity_signals}
                has_vacancy = "vacant_property" in prop_signal_types
                has_distress = bool(prop_signal_types & {"tax_delinquent", "distress", "estate_ownership"})
                has_availability = _has_availability_keywords(prop.land_use)
                if not has_vacancy and not has_distress and not has_availability:
                    logger.debug(f"Filtered established business: {prop.address} (built {prop.year_built})")
                    continue
        
        # Parcel size filter (scraped listings already size-filtered during import)
        if prop.lot_size_acres and not is_scraped:
            if prop.lot_size_acres < min_parcel_acres or prop.lot_size_acres > max_parcel_acres:
                continue
        
        # Building size filter (if building exists)
        if prop.sqft:
            # If it's not land, check building size
            if prop.property_type != PropertyType.LAND:
                if min_building_sqft and prop.sqft < min_building_sqft:
                    continue
                if max_building_sqft and prop.sqft > max_building_sqft:
                    continue
        
        # Exclude multi-tenant buildings (use heuristics)
        # - If building is very large (>10,000 sqft) and retail/office, likely multi-tenant
        # - If description/signals mention "multi-tenant" or "shopping center" or "strip mall"
        if prop.sqft and prop.sqft > 10000:
            # Large buildings are likely multi-tenant unless it's a warehouse/single-user
            signal_descriptions = " ".join([s.description.lower() for s in prop.opportunity_signals])
            if any(term in signal_descriptions for term in ["multi", "center", "plaza", "strip"]):
                continue
        
        # Opportunity signal filter — require at least one HIGH or MEDIUM strength signal
        # LAND properties are exempt (empty land is inherently an opportunity)
        if require_opportunity_signal and prop.property_type != PropertyType.LAND:
            meaningful = [s for s in prop.opportunity_signals if s.strength in ("high", "medium")]
            if not meaningful:
                continue
        
        # Minimum opportunity score
        if prop.opportunity_score and prop.opportunity_score < min_opportunity_score:
            continue
        
        filtered.append(prop)
    
    return filtered


@router.post("/search", response_model=OpportunitySearchResponse)
async def search_opportunities(request: OpportunitySearchRequest, db: Session = Depends(get_db)):
    """
    Search for CSOKi-qualified property opportunities using ATTOM data.
    
    This endpoint applies CSOKi's specific criteria:
    - Parcel size: 0.8-2 acres (configurable)
    - Building size: 2500-6000 sqft if building exists (configurable)
    - Property types: Retail (preferred), Office (acceptable), Land (empty parcels)
    - Focus: Empty parcels OR vacant single-tenant buildings
    - Exclude: Multi-tenant buildings (estimated via size + property type)
    - Proximity: Must be within 1 mile of a Verizon-family store
      (Russell Cellular, Victra, Verizon Corporate)
    
    Results are ranked by opportunity priority:
    1. Empty parcels (land only)
    2. Vacant properties
    3. Out-of-state/absentee owners
    4. Tax liens/pressure
    5. Aging owners (65+)
    6. Small single-tenant buildings
    
    Returns properties as map pins with signal count and ranking.
    """
    if not settings.ATTOM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ATTOM API key not configured. Please set ATTOM_API_KEY environment variable."
        )
    
    # Create bounds
    bounds = GeoBounds(
        min_lat=request.min_lat,
        max_lat=request.max_lat,
        min_lng=request.min_lng,
        max_lng=request.max_lng,
    )
    
    # Build property types list
    property_types = []
    if request.include_retail:
        property_types.append(PropertyType.RETAIL)
    if request.include_office:
        property_types.append(PropertyType.OFFICE)
    if request.include_land:
        property_types.append(PropertyType.LAND)
    
    if not property_types:
        raise HTTPException(
            status_code=400,
            detail="Must include at least one property type (retail, office, or land)"
        )
    
    try:
        # Search ATTOM API
        result: PropertySearchResult = await attom_search_bounds(
            bounds=bounds,
            property_types=property_types,
            min_opportunity_score=0,  # We'll filter after
            limit=request.limit * 2,  # Request extra to account for filtering
        )

        # Also fetch scraped listings (Crexi/LoopNet) — confirmed for-lease
        scraped_properties = _fetch_scraped_listings(
            db=db,
            bounds=bounds,
            min_parcel_acres=request.min_parcel_acres,
            max_parcel_acres=request.max_parcel_acres,
            min_building_sqft=request.min_building_sqft,
            max_building_sqft=request.max_building_sqft,
            include_retail=request.include_retail,
            include_office=request.include_office,
            include_land=request.include_land,
        )

        # Merge sources, deduplicating overlapping properties
        all_properties = _merge_and_deduplicate(result.properties, scraped_properties)

        # Apply CSOKi-specific filters
        filtered_properties = _filter_properties_for_opportunities(
            properties=all_properties,
            min_parcel_acres=request.min_parcel_acres,
            max_parcel_acres=request.max_parcel_acres,
            min_building_sqft=request.min_building_sqft,
            max_building_sqft=request.max_building_sqft,
            include_retail=request.include_retail,
            include_office=request.include_office,
            include_land=request.include_land,
            require_opportunity_signal=request.require_opportunity_signal,
            min_opportunity_score=request.min_opportunity_score,
        )
        
        # Keep only properties near a Verizon-family store
        # Scraped listings (user-curated imports) always bypass this filter
        if request.max_verizon_family_distance > 0:
            scraped = [p for p in filtered_properties if p.source in (PropertySource.CREXI, PropertySource.LOOPNET)]
            non_scraped = [p for p in filtered_properties if p.source not in (PropertySource.CREXI, PropertySource.LOOPNET)]

            non_scraped = _filter_by_verizon_family_proximity(
                properties=non_scraped,
                db=db,
                bounds_min_lat=request.min_lat,
                bounds_max_lat=request.max_lat,
                bounds_min_lng=request.min_lng,
                bounds_max_lng=request.max_lng,
                max_distance_miles=request.max_verizon_family_distance,
            )

            filtered_properties = scraped + non_scraped

        # --- Market Viability Hard Filters + Data Fetching ---

        # 1. Corporate store distances (DB-only, zero API cost)
        corporate_distances: dict[str, float] = {}
        corporate_store_count = 0
        if request.enable_corporate_distance_scoring:
            corporate_distances, corporate_store_count = _calculate_corporate_store_distances(
                properties=filtered_properties,
                db=db,
                bounds_min_lat=request.min_lat,
                bounds_max_lat=request.max_lat,
                bounds_min_lng=request.min_lng,
                bounds_max_lng=request.max_lng,
            )

        # 2. HARD FILTER: minimum 3mi gap from Verizon Corporate stores
        if corporate_distances:
            before_count = len(filtered_properties)
            filtered_properties = [
                p for p in filtered_properties
                if corporate_distances.get(p.id, 999.0) >= 3.0
            ]
            removed = before_count - len(filtered_properties)
            if removed:
                logger.info(f"Corporate gap filter removed {removed} properties within 3mi of Verizon Corporate")

        # 3. Fetch viewport-center demographics (1 ArcGIS call, cached 24hr)
        population_data: dict[str, dict] = {}
        viewport_population = None
        center_lat = (request.min_lat + request.max_lat) / 2
        center_lng = (request.min_lng + request.max_lng) / 2

        if request.enable_population_scoring:
            cached_demo = get_cached_demographics(center_lat, center_lng)
            if cached_demo:
                viewport_population = cached_demo
            else:
                try:
                    demo_response = await fetch_demographics(center_lat, center_lng, radii_miles=[1, 3])
                    viewport_population = {
                        "pop_1mi": demo_response.radii[0].total_population,
                        "pop_3mi": demo_response.radii[1].total_population,
                        "income_3mi": demo_response.radii[1].median_household_income,
                    }
                    cache_demographics(center_lat, center_lng, viewport_population)
                except Exception as e:
                    logger.warning(f"ArcGIS demographics failed (non-fatal): {e}")

        # 4. HARD FILTER: population >= 12K within 3mi (market viability)
        if viewport_population and (viewport_population.get("pop_3mi") or 0) < 12000:
            before_count = len(filtered_properties)
            filtered_properties = [
                p for p in filtered_properties
                if p.property_type == PropertyType.LAND
                or p.source in (PropertySource.CREXI, PropertySource.LOOPNET)
            ]
            removed = before_count - len(filtered_properties)
            logger.info(
                f"Low-population market ({viewport_population.get('pop_3mi')} within 3mi). "
                f"Removed {removed} non-land/non-scraped properties."
            )

        # Populate population_data for scoring (viewport-level data applied to all properties)
        if viewport_population:
            for prop in filtered_properties:
                population_data[prop.id] = {
                    "pop_1mi": viewport_population.get("pop_1mi"),
                    "pop_3mi": viewport_population.get("pop_3mi"),
                }

        # 5. Fetch retail anchor stores near viewport center (1 Mapbox call, cached 1hr)
        retail_node_data: dict[str, dict] = {}
        retail_nodes_found = 0
        anchor_pois: list[dict] = []

        if request.enable_retail_node_scoring:
            cached_nodes = get_cached_retail_nodes(center_lat, center_lng)
            if cached_nodes is not None:
                anchor_pois = cached_nodes
            else:
                try:
                    anchor_result = await fetch_mapbox_pois(
                        center_lat, center_lng,
                        radius_meters=2414,  # 1.5 miles — catches anchors slightly outside viewport
                        categories=["anchors"],
                    )
                    anchor_pois = [
                        {"name": poi.name, "lat": poi.latitude, "lng": poi.longitude}
                        for poi in anchor_result.pois
                    ]
                    cache_retail_nodes(center_lat, center_lng, anchor_pois)
                except Exception as e:
                    logger.warning(f"Mapbox anchor search failed (non-fatal): {e}")

        # 6. HARD FILTER: must be within 1mi of a retail anchor
        if anchor_pois:
            retail_nodes_found = len(anchor_pois)
            surviving = []
            for prop in filtered_properties:
                nearest_dist = None
                nearest_name = None
                for anchor in anchor_pois:
                    d = haversine(prop.longitude, prop.latitude, anchor["lng"], anchor["lat"])
                    if nearest_dist is None or d < nearest_dist:
                        nearest_dist = d
                        nearest_name = anchor["name"]
                retail_node_data[prop.id] = {"distance": nearest_dist, "name": nearest_name}

                # LAND and scraped listings exempt from anchor proximity requirement
                is_exempt = (
                    prop.property_type == PropertyType.LAND
                    or prop.source in (PropertySource.CREXI, PropertySource.LOOPNET)
                )
                if is_exempt or (nearest_dist is not None and nearest_dist <= 1.0):
                    surviving.append(prop)
                else:
                    logger.debug(
                        f"Filtered no anchor proximity: {prop.address} "
                        f"(nearest: {nearest_dist:.2f}mi to {nearest_name})"
                    )
            filtered_properties = surviving

        # Calculate priority ranking for each property with market viability data
        ranked_opportunities = []
        for prop in filtered_properties:
            corp_dist = corporate_distances.get(prop.id)
            pop_info = population_data.get(prop.id, {})
            retail_info = retail_node_data.get(prop.id, {})

            rank_score, priority_signals = _calculate_priority_rank(
                prop,
                nearest_corporate_distance=corp_dist,
                nearest_retail_node_distance=retail_info.get("distance"),
                area_population_1mi=pop_info.get("pop_1mi"),
                area_population_3mi=pop_info.get("pop_3mi"),
            )
            ranked_opportunities.append({
                "property": prop,
                "rank_score": rank_score,
                "priority_signals": priority_signals,
                "signal_count": len(prop.opportunity_signals),
                "nearest_corporate_store_miles": corp_dist,
                "nearest_retail_node_miles": retail_info.get("distance"),
                "nearest_retail_node_name": retail_info.get("name"),
                "area_population_1mi": pop_info.get("pop_1mi"),
                "area_population_3mi": pop_info.get("pop_3mi"),
            })

        # Sort by rank score (highest first)
        ranked_opportunities.sort(key=lambda x: x["rank_score"], reverse=True)

        # Apply limit after ranking
        ranked_opportunities = ranked_opportunities[:request.limit]

        # Convert to response format with 1-based ranking
        opportunities = [
            OpportunityRanking(
                property=opp["property"],
                rank=idx + 1,
                priority_signals=opp["priority_signals"],
                signal_count=opp["signal_count"],
                nearest_corporate_store_miles=opp["nearest_corporate_store_miles"],
                nearest_retail_node_miles=opp["nearest_retail_node_miles"],
                nearest_retail_node_name=opp["nearest_retail_node_name"],
                area_population_1mi=opp["area_population_1mi"],
                area_population_3mi=opp["area_population_3mi"],
            )
            for idx, opp in enumerate(ranked_opportunities)
        ]

        # Calculate center point
        center_lat = (request.min_lat + request.max_lat) / 2
        center_lng = (request.min_lng + request.max_lng) / 2

        return OpportunitySearchResponse(
            center_latitude=center_lat,
            center_longitude=center_lng,
            total_found=len(opportunities),
            opportunities=opportunities,
            search_timestamp=datetime.now().isoformat(),
            filters_applied={
                "parcel_size_acres": f"{request.min_parcel_acres}-{request.max_parcel_acres}",
                "building_size_sqft": f"{request.min_building_sqft}-{request.max_building_sqft}" if request.min_building_sqft else "Any",
                "property_types": [
                    pt for pt, include in [
                        ("retail", request.include_retail),
                        ("office", request.include_office),
                        ("land", request.include_land),
                    ] if include
                ],
                "min_opportunity_score": request.min_opportunity_score,
                "max_verizon_family_distance_miles": request.max_verizon_family_distance,
                "corporate_distance_scoring": request.enable_corporate_distance_scoring,
                "population_scoring": request.enable_population_scoring,
                "retail_node_scoring": request.enable_retail_node_scoring,
            },
            corporate_stores_in_area=corporate_store_count,
            retail_nodes_found=retail_nodes_found,
        )
    
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching opportunities: {str(e)}")


@router.get("/stats")
async def get_opportunity_stats():
    """
    Get statistics about opportunity signals and their meanings.
    
    Returns metadata about what each opportunity signal means and
    how properties are ranked.
    """
    return {
        "priority_order": [
            {
                "rank": 1,
                "signal": "Empty parcels (land only)",
                "description": "Vacant land parcels ready for development",
                "points": 100
            },
            {
                "rank": 2,
                "signal": "Vacant properties",
                "description": "Properties currently unoccupied",
                "points": 80
            },
            {
                "rank": 3,
                "signal": "Out-of-state/absentee owners",
                "description": "Owner lives in different state, less attachment",
                "points": 60
            },
            {
                "rank": 4,
                "signal": "Tax liens/pressure",
                "description": "Tax delinquency or recent tax increases",
                "points": 50
            },
            {
                "rank": 5,
                "signal": "Aging owners (65+)",
                "description": "Estate or trust ownership, potential succession",
                "points": 40
            },
            {
                "rank": 6,
                "signal": "Small single-tenant buildings",
                "description": "2500-6000 sqft buildings, ideal size for conversion",
                "points": 30
            }
        ],
        "bonus_signals": [
            {
                "signal": "Foreclosure/distress",
                "description": "Property in foreclosure or pre-foreclosure",
                "points": 70
            }
        ],
        "criteria": {
            "parcel_size": "0.8-2 acres",
            "building_size": "2500-6000 sqft (if building exists)",
            "property_types": ["Retail (preferred)", "Office (acceptable)", "Land (empty parcels)"],
            "excludes": ["Multi-tenant buildings", "Shopping centers", "Strip malls"],
            "proximity_to_verizon_family": "Within 1 mile of Russell Cellular, Victra, or Verizon Corporate"
        },
        "market_viability_scoring": {
            "corporate_store_distance": [
                {"condition": "7+ miles from Verizon Corporate", "points": 20, "label": "Excellent corporate gap"},
                {"condition": "5-7 miles from Verizon Corporate", "points": 15, "label": "Strong corporate gap"},
                {"condition": "3-5 miles (high-pop) or 5+ miles (low-pop)", "points": 10, "label": "Adequate corporate gap"},
                {"condition": "Below threshold", "points": 0, "label": "No bonus"},
            ],
            "population_threshold": [
                {"condition": "12K+ within 1 mile", "points": 20, "label": "Strong population density"},
                {"condition": "25K+ within 3 miles (bonus)", "points": 5, "label": "High-density market"},
                {"condition": "12K+ within 3 miles only", "points": 10, "label": "Viable population"},
            ],
            "retail_node_proximity": [
                {"condition": "Major retail anchor within 0.25mi", "points": 25, "label": "Adjacent to major retail anchor"},
                {"condition": "Major retail anchor within 0.5mi", "points": 15, "label": "Near major retail anchor"},
                {"condition": "Major retail anchor within 1.0mi", "points": 5, "label": "Retail anchor within 1mi"},
            ],
            "population_threshold_note": "High-pop market = 12K+ within 3mi (3mi corporate gap acceptable). Low-pop = under 12K (5mi corporate gap expected).",
        }
    }
