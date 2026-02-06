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
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from math import radians, cos, sin, asin, sqrt

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

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

# Verizon-family brands that CSOKi opportunities must be distant from
VERIZON_FAMILY_BRANDS = ["russell_cellular", "victra", "verizon_corporate"]


def _haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great circle distance in miles between two points on earth."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return c * 3956  # Earth radius in miles


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
            dist = _haversine(prop.longitude, prop.latitude, store.longitude, store.latitude)
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

    limit: int = Field(default=100, le=500, description="Maximum results to return")


class OpportunityRanking(BaseModel):
    """Enhanced opportunity metadata with ranking."""
    property: PropertyListing
    rank: int  # 1-based ranking (1 = highest priority)
    priority_signals: List[str]  # Which high-priority signals are present
    signal_count: int  # Total number of signals


class OpportunitySearchResponse(BaseModel):
    """Response for opportunity search."""
    center_latitude: float
    center_longitude: float
    total_found: int
    opportunities: List[OpportunityRanking]
    search_timestamp: str
    filters_applied: dict


def _calculate_priority_rank(listing: PropertyListing) -> tuple[int, List[str]]:
    """
    Calculate priority rank based on opportunity signals.
    
    Returns (rank_score, priority_signals)
    Higher rank_score = higher priority
    
    Priority Order:
    1. Empty parcels (land only) - 100 points
    2. Vacant properties - 80 points
    3. Out-of-state/absentee owners - 60 points
    4. Tax liens/pressure - 50 points
    5. Aging owners (65+) - 40 points
    6. Small single-tenant buildings - 30 points
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
    
    # 6. Small single-tenant buildings
    if listing.property_type in (PropertyType.RETAIL, PropertyType.OFFICE):
        if listing.sqft and 2500 <= listing.sqft <= 6000:
            rank_score += 30
            priority_signals.append("Small single-tenant building")
    
    # Bonus: Distressed properties (foreclosure, etc.)
    if "distress" in signal_types:
        rank_score += 70
        priority_signals.append("Foreclosure/distress")
    
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

        # Calculate priority ranking for each property
        ranked_opportunities = []
        for prop in filtered_properties:
            rank_score, priority_signals = _calculate_priority_rank(prop)
            ranked_opportunities.append({
                "property": prop,
                "rank_score": rank_score,
                "priority_signals": priority_signals,
                "signal_count": len(prop.opportunity_signals),
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
            }
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
        }
    }
