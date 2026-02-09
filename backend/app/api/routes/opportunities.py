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
    OpportunitySignal,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.store import Store
from app.utils.geo import haversine
from app.services.viewport_cache import (
    get_cached_demographics,
    cache_demographics,
    get_cached_retail_nodes,
    cache_retail_nodes,
)

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

# Land use keywords indicating especially promising conversion candidates
BOOSTED_LAND_USE_KEYWORDS = {
    "vacant", "former", "closed", "abandoned", "retail store", "commercial",
    "general retail", "strip", "shopping", "storefront", "office building",
    "professional office", "mixed use",
}


def _is_excluded_land_use(land_use: str | None) -> bool:
    """Check if a property's land use indicates an incompatible commercial use."""
    if not land_use:
        return False
    land_use_lower = land_use.lower()
    return any(keyword in land_use_lower for keyword in EXCLUDED_LAND_USE_KEYWORDS)


def _is_boosted_land_use(land_use: str | None) -> bool:
    """Check if a property's land use indicates an especially promising conversion candidate."""
    if not land_use:
        return False
    land_use_lower = land_use.lower()
    return any(keyword in land_use_lower for keyword in BOOSTED_LAND_USE_KEYWORDS)


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

    if not verizon_stores:
        return []

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
    7. Occupied building penalty - -150 points (no vacancy indicators)

    Market Viability (additive):
    - Corporate store gap: up to +20 points
    - Population density: up to +25 points
    - Retail node proximity: up to +25 points
    """
    rank_score = 0
    priority_signals = []

    signal_types = {s.signal_type for s in listing.opportunity_signals}

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

    # 6. Small single-tenant buildings (land-use-aware scoring)
    if listing.property_type in (PropertyType.RETAIL, PropertyType.OFFICE):
        if listing.sqft and 2500 <= listing.sqft <= 6000:
            if _is_boosted_land_use(listing.land_use):
                rank_score += 40
                priority_signals.append("Ideal small building (vacant/retail)")
            elif listing.land_use:
                rank_score += 30
                priority_signals.append(f"Small single-tenant building ({listing.land_use})")
            else:
                rank_score += 25
                priority_signals.append("Small single-tenant building")

    # 7. Occupied building penalty
    # Core rule: we want EMPTY PARCELS and FOR-LEASE buildings, not active businesses.
    # Any built structure without vacancy indicators is likely occupied → heavy penalty.
    if listing.property_type != PropertyType.LAND:
        has_vacancy = "vacant_property" in signal_types
        has_boosted_use = _is_boosted_land_use(listing.land_use)  # "vacant", "former", "closed", etc.
        if has_vacancy or has_boosted_use:
            # Vacant/for-lease building — this is a valid opportunity, small boost
            if not has_vacancy:  # boosted land use but no ATTOM vacancy signal
                rank_score += 20
                priority_signals.append(f"Potential vacancy ({listing.land_use})")
        else:
            # Occupied building — not what we're looking for
            rank_score -= 150
            if listing.land_use:
                priority_signals.append(f"Occupied building ({listing.land_use})")
            else:
                priority_signals.append("Occupied building (no vacancy indicators)")

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
        
        # Parcel size filter
        if prop.lot_size_acres:
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
        
        # Opportunity signal filter
        if require_opportunity_signal and not prop.opportunity_signals:
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
        
        # Apply CSOKi-specific filters
        filtered_properties = _filter_properties_for_opportunities(
            properties=result.properties,
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
        if request.max_verizon_family_distance > 0:
            filtered_properties = _filter_by_verizon_family_proximity(
                properties=filtered_properties,
                db=db,
                bounds_min_lat=request.min_lat,
                bounds_max_lat=request.max_lat,
                bounds_min_lng=request.min_lng,
                bounds_max_lng=request.max_lng,
                max_distance_miles=request.max_verizon_family_distance,
            )

        # --- Market Viability Data Fetching ---

        # Corporate store distances (DB-only, zero API cost)
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

        # Population data (Phase 2 - will be fetched via ArcGIS with caching)
        population_data: dict[str, dict] = {}  # property_id -> {pop_1mi, pop_3mi}

        # Retail node data (Phase 3 - will be fetched via Mapbox Places with caching)
        retail_node_data: dict[str, dict] = {}  # property_id -> {distance, name}
        retail_nodes_found = 0

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
