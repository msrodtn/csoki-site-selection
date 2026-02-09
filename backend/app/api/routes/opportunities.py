"""
Opportunities API - Site-quality-first property ranking for CSOKi.

Finds the best AVAILABLE sites for a new Cellular Sales store by:

Eligibility (3 categories):
  A. Vacant land parcels (ATTOM, 0.8-2 acres)
  B. For-lease listings (Crexi/LoopNet imports)
  C. Vacant retail/office buildings (ATTOM, 2500-6000 sqft, vacancy evidence)

Ranking (site quality first):
  1. Population density (up to 40 pts)
  2. Retail anchor proximity (up to 35 pts)
  3. Verizon Corporate gap distance (up to 25 pts)
  4. Availability quality (up to 35 pts)
  5. Size fit (up to 15 pts)
  6. VZ family co-location bonus (up to 10 pts)
  7. Distress tiebreaker (up to 10 pts)
"""

import logging

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

# Verizon-family brands for co-location scoring
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

# Land use keywords indicating availability (vacant, former, closed, etc.)
AVAILABILITY_LAND_USE_KEYWORDS = {
    "vacant", "former", "closed", "abandoned", "demolished", "unused",
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


def _calculate_verizon_family_distances(
    properties: List[PropertyListing],
    db: Session,
    bounds_min_lat: float,
    bounds_max_lat: float,
    bounds_min_lng: float,
    bounds_max_lng: float,
) -> tuple[dict[str, tuple[float, str]], int]:
    """
    Calculate distance from each property to the nearest Verizon-family store
    (Russell Cellular, Victra, or Verizon Corporate).

    Returns:
        (distance_map, store_count) where distance_map is
        {property_id: (miles, brand_name)}
    """
    buffer_miles = 5.0
    lat_buffer = buffer_miles / 69.0
    lng_buffer = buffer_miles / 55.0

    vz_stores = db.query(Store).filter(
        Store.brand.in_(VERIZON_FAMILY_BRANDS),
        Store.latitude.isnot(None),
        Store.longitude.isnot(None),
        Store.latitude >= bounds_min_lat - lat_buffer,
        Store.latitude <= bounds_max_lat + lat_buffer,
        Store.longitude >= bounds_min_lng - lng_buffer,
        Store.longitude <= bounds_max_lng + lng_buffer,
    ).all()

    distance_map: dict[str, tuple[float, str]] = {}
    for prop in properties:
        if prop.latitude is None or prop.longitude is None:
            continue
        if not vz_stores:
            distance_map[prop.id] = (999.0, "none")
            continue
        nearest_dist = None
        nearest_brand = ""
        for store in vz_stores:
            d = haversine(prop.longitude, prop.latitude, store.longitude, store.latitude)
            if nearest_dist is None or d < nearest_dist:
                nearest_dist = d
                nearest_brand = store.brand
        distance_map[prop.id] = (round(nearest_dist, 2), nearest_brand)

    return distance_map, len(vz_stores)


# ---------------------------------------------------------------------------
# Eligibility filter — 3 clear categories
# ---------------------------------------------------------------------------

def _filter_properties_for_opportunities(
    properties: List[PropertyListing],
    min_parcel_acres: float,
    max_parcel_acres: float,
    min_building_sqft: Optional[float],
    max_building_sqft: Optional[float],
    include_retail: bool,
    include_office: bool,
    include_land: bool,
) -> List[PropertyListing]:
    """
    Apply CSOKi eligibility filter with 3 categories:

    Category A — Vacant Land (ATTOM):
        property_type == LAND, lot 0.8-2ac, not excluded land use

    Category B — For-Lease Listings (Crexi/LoopNet):
        Already confirmed available, size-filtered during import

    Category C — Vacant Retail/Office (ATTOM):
        property_type in (RETAIL, OFFICE), building 2500-6000 sqft,
        must have vacancy evidence, not excluded land use, not multi-tenant
    """
    filtered = []

    for prop in properties:
        # Property type gate — only retail, office, and land
        if prop.property_type == PropertyType.RETAIL and not include_retail:
            continue
        if prop.property_type == PropertyType.OFFICE and not include_office:
            continue
        if prop.property_type == PropertyType.LAND and not include_land:
            continue
        if prop.property_type not in (PropertyType.RETAIL, PropertyType.OFFICE, PropertyType.LAND):
            continue

        is_scraped = prop.source in (PropertySource.CREXI, PropertySource.LOOPNET)

        # --- Category B: For-lease listings pass through ---
        if is_scraped:
            filtered.append(prop)
            continue

        # Excluded land uses apply to all ATTOM properties
        if _is_excluded_land_use(prop.land_use):
            continue

        # --- Category A: Vacant Land ---
        if prop.property_type == PropertyType.LAND:
            # Lot size filter
            if prop.lot_size_acres:
                if prop.lot_size_acres < min_parcel_acres or prop.lot_size_acres > max_parcel_acres:
                    continue
            filtered.append(prop)
            continue

        # --- Category C: Vacant Retail/Office ---
        if prop.property_type in (PropertyType.RETAIL, PropertyType.OFFICE):
            # Building size filter
            if prop.sqft:
                if min_building_sqft and prop.sqft < min_building_sqft:
                    continue
                if max_building_sqft and prop.sqft > max_building_sqft:
                    continue

            # Multi-tenant heuristic
            if prop.sqft and prop.sqft > 10000:
                signal_descriptions = " ".join(
                    [s.description.lower() for s in prop.opportunity_signals]
                )
                land_use_lower = (prop.land_use or "").lower()
                if any(
                    term in signal_descriptions or term in land_use_lower
                    for term in ["multi", "center", "plaza", "strip"]
                ):
                    continue

            # Must have vacancy evidence
            prop_signal_types = {s.signal_type for s in prop.opportunity_signals}
            has_vacancy = "vacant_property" in prop_signal_types
            has_availability = _has_availability_keywords(prop.land_use)
            if not has_vacancy and not has_availability:
                continue

            filtered.append(prop)

    logger.info(
        f"Eligibility filter: {len(filtered)} of {len(properties)} passed "
        f"(scraped={sum(1 for p in filtered if p.source in (PropertySource.CREXI, PropertySource.LOOPNET))}, "
        f"land={sum(1 for p in filtered if p.property_type == PropertyType.LAND)}, "
        f"vacant_bldg={sum(1 for p in filtered if p.property_type in (PropertyType.RETAIL, PropertyType.OFFICE) and p.source not in (PropertySource.CREXI, PropertySource.LOOPNET))})"
    )
    return filtered


# ---------------------------------------------------------------------------
# Site-quality-first scoring
# ---------------------------------------------------------------------------

def _calculate_priority_rank(
    listing: PropertyListing,
    nearest_corporate_distance: Optional[float] = None,
    nearest_retail_node_distance: Optional[float] = None,
    nearest_vz_family_distance: Optional[float] = None,
    area_population_1mi: Optional[int] = None,
    area_population_3mi: Optional[int] = None,
) -> tuple[int, List[str]]:
    """
    Calculate site-quality-first ranking score.

    Returns (rank_score, priority_signals)
    Higher rank_score = higher priority

    Site Quality (up to 100 pts):
      - Population density: up to 40
      - Retail anchor proximity: up to 35
      - Corporate gap: up to 25

    Availability Quality (up to 35 pts):
      - Active listing: 35
      - Vacant land: 25
      - Confirmed vacant building: 15-20

    Size Fit (up to 15 pts):
      - Ideal lot/building size: 10-15

    VZ Family Co-location (up to 10 pts)
    Distress tiebreaker (up to 10 pts)
    """
    rank_score = 0
    priority_signals = []

    signal_types = {s.signal_type for s in listing.opportunity_signals}

    # === SITE QUALITY (up to 100 pts) ===

    # Population density — up to 40 pts
    if area_population_1mi is not None and area_population_1mi >= 12000:
        rank_score += 30
        priority_signals.append(f"Strong population ({area_population_1mi:,} within 1mi)")
        if (area_population_3mi or 0) >= 25000:
            rank_score += 10
            priority_signals.append(f"High-density market ({area_population_3mi:,} within 3mi)")
    elif area_population_3mi is not None and area_population_3mi >= 12000:
        rank_score += 15
        priority_signals.append(f"Viable population ({area_population_3mi:,} within 3mi)")
        if area_population_3mi >= 25000:
            rank_score += 10
            priority_signals.append(f"High-density market ({area_population_3mi:,} within 3mi)")

    # Retail anchor proximity — up to 35 pts
    if nearest_retail_node_distance is not None:
        if nearest_retail_node_distance <= 0.25:
            rank_score += 35
            priority_signals.append("Adjacent to major retail anchor")
        elif nearest_retail_node_distance <= 0.5:
            rank_score += 25
            priority_signals.append("Near major retail anchor (<0.5mi)")
        elif nearest_retail_node_distance <= 1.0:
            rank_score += 10
            priority_signals.append("Retail anchor within 1mi")

    # Verizon Corporate gap — up to 25 pts
    if nearest_corporate_distance is not None:
        is_high_pop = (area_population_3mi or 0) >= 12000
        min_threshold = 3.0 if is_high_pop else 5.0

        if nearest_corporate_distance >= 7.0:
            rank_score += 25
            priority_signals.append(f"Excellent corporate gap ({nearest_corporate_distance:.1f}mi)")
        elif nearest_corporate_distance >= 5.0:
            rank_score += 20
            priority_signals.append(f"Strong corporate gap ({nearest_corporate_distance:.1f}mi)")
        elif nearest_corporate_distance >= min_threshold:
            rank_score += 10
            priority_signals.append(f"Adequate corporate gap ({nearest_corporate_distance:.1f}mi)")

    # === AVAILABILITY QUALITY (up to 35 pts) ===

    if listing.source in (PropertySource.CREXI, PropertySource.LOOPNET):
        rank_score += 35
        source_label = listing.source.value.title()
        priority_signals.append(f"Active for-lease listing ({source_label})")
    elif listing.property_type == PropertyType.LAND:
        rank_score += 25
        priority_signals.append("Vacant land (buildable)")
    else:
        # Vacant retail/office
        has_vacancy = "vacant_property" in signal_types
        has_availability = _has_availability_keywords(listing.land_use)
        if has_vacancy and has_availability:
            rank_score += 20
            priority_signals.append(f"Confirmed vacant ({listing.land_use})")
        elif has_vacancy:
            rank_score += 15
            priority_signals.append("Vacant building")
        elif has_availability:
            rank_score += 15
            priority_signals.append(f"Available ({listing.land_use})")

    # === SIZE FIT (up to 15 pts) ===

    if listing.property_type == PropertyType.LAND and listing.lot_size_acres:
        if 0.8 <= listing.lot_size_acres <= 1.2:
            rank_score += 15
            priority_signals.append(f"Ideal lot size ({listing.lot_size_acres:.1f}ac)")
        elif listing.lot_size_acres <= 2.0:
            rank_score += 10
            priority_signals.append(f"Acceptable lot size ({listing.lot_size_acres:.1f}ac)")
    elif listing.sqft and listing.property_type in (PropertyType.RETAIL, PropertyType.OFFICE):
        if 2500 <= listing.sqft <= 3500:
            rank_score += 15
            priority_signals.append(f"Ideal building size ({listing.sqft:,.0f} sqft)")
        elif listing.sqft <= 6000:
            rank_score += 10
            priority_signals.append(f"Acceptable building size ({listing.sqft:,.0f} sqft)")

    # === VZ FAMILY CO-LOCATION BONUS (up to 10 pts) ===

    if nearest_vz_family_distance is not None:
        if nearest_vz_family_distance <= 0.5:
            rank_score += 10
            priority_signals.append(f"Near VZ-family store ({nearest_vz_family_distance:.1f}mi)")
        elif nearest_vz_family_distance <= 1.0:
            rank_score += 5
            priority_signals.append(f"VZ-family store within 1mi")

    # === DISTRESS TIEBREAKER (up to 10 pts) ===

    if "tax_delinquent" in signal_types or "distress" in signal_types:
        rank_score += 10
        if "distress" in signal_types:
            priority_signals.append("Foreclosure/distress")
        else:
            priority_signals.append("Tax delinquent")
    elif "absentee_owner" in signal_types:
        rank_score += 5
        priority_signals.append("Absentee owner")

    return rank_score, priority_signals


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

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
    priority_signals: List[str]  # Which scoring signals are present
    signal_count: int  # Total number of ATTOM signals

    # Market viability enrichment
    nearest_corporate_store_miles: Optional[float] = None
    nearest_retail_node_miles: Optional[float] = None
    nearest_retail_node_name: Optional[str] = None
    nearest_verizon_family_miles: Optional[float] = None
    nearest_verizon_family_name: Optional[str] = None
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
    verizon_family_stores_in_area: int = 0
    retail_nodes_found: int = 0
    viewport_population_center: Optional[dict] = None


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@router.post("/search", response_model=OpportunitySearchResponse)
async def search_opportunities(request: OpportunitySearchRequest, db: Session = Depends(get_db)):
    """
    Search for CSOKi-qualified property opportunities.

    Finds available sites (vacant land, for-lease listings, vacant buildings)
    and ranks them by site quality: population density, retail anchor proximity,
    corporate gap distance, and size fit.
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
        # 1. Search ATTOM API
        result: PropertySearchResult = await attom_search_bounds(
            bounds=bounds,
            property_types=property_types,
            min_opportunity_score=0,
            limit=request.limit * 2,
        )

        # 2. Fetch scraped listings (Crexi/LoopNet)
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

        # 3. Merge + deduplicate
        all_properties = _merge_and_deduplicate(result.properties, scraped_properties)

        # 4. Apply eligibility filter
        filtered_properties = _filter_properties_for_opportunities(
            properties=all_properties,
            min_parcel_acres=request.min_parcel_acres,
            max_parcel_acres=request.max_parcel_acres,
            min_building_sqft=request.min_building_sqft,
            max_building_sqft=request.max_building_sqft,
            include_retail=request.include_retail,
            include_office=request.include_office,
            include_land=request.include_land,
        )

        # --- Market viability data fetching (for scoring) ---

        center_lat = (request.min_lat + request.max_lat) / 2
        center_lng = (request.min_lng + request.max_lng) / 2

        # 5a. Corporate store distances (DB-only)
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

        # 5b. VZ family distances for co-location scoring (DB-only)
        vz_family_distances: dict[str, tuple[float, str]] = {}
        vz_family_store_count = 0
        vz_family_distances, vz_family_store_count = _calculate_verizon_family_distances(
            properties=filtered_properties,
            db=db,
            bounds_min_lat=request.min_lat,
            bounds_max_lat=request.max_lat,
            bounds_min_lng=request.min_lng,
            bounds_max_lng=request.max_lng,
        )

        # 6. Fetch viewport-center demographics (1 ArcGIS call, cached 24hr)
        population_data: dict[str, dict] = {}
        viewport_population = None

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

        if viewport_population:
            for prop in filtered_properties:
                population_data[prop.id] = {
                    "pop_1mi": viewport_population.get("pop_1mi"),
                    "pop_3mi": viewport_population.get("pop_3mi"),
                }

        # 7. Fetch retail anchor stores near viewport center (1 Mapbox call, cached 1hr)
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
                        radius_meters=2414,  # 1.5 miles
                        categories=["anchors"],
                    )
                    anchor_pois = [
                        {"name": poi.name, "lat": poi.latitude, "lng": poi.longitude}
                        for poi in anchor_result.pois
                    ]
                    cache_retail_nodes(center_lat, center_lng, anchor_pois)
                except Exception as e:
                    logger.warning(f"Mapbox anchor search failed (non-fatal): {e}")

        if anchor_pois:
            retail_nodes_found = len(anchor_pois)
            for prop in filtered_properties:
                nearest_dist = None
                nearest_name = None
                for anchor in anchor_pois:
                    d = haversine(prop.longitude, prop.latitude, anchor["lng"], anchor["lat"])
                    if nearest_dist is None or d < nearest_dist:
                        nearest_dist = d
                        nearest_name = anchor["name"]
                retail_node_data[prop.id] = {"distance": nearest_dist, "name": nearest_name}

        # 8. Score each property with site-quality-first formula
        ranked_opportunities = []
        for prop in filtered_properties:
            corp_dist = corporate_distances.get(prop.id)
            pop_info = population_data.get(prop.id, {})
            retail_info = retail_node_data.get(prop.id, {})
            vz_info = vz_family_distances.get(prop.id)

            rank_score, priority_signals = _calculate_priority_rank(
                prop,
                nearest_corporate_distance=corp_dist,
                nearest_retail_node_distance=retail_info.get("distance"),
                nearest_vz_family_distance=vz_info[0] if vz_info else None,
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
                "nearest_verizon_family_miles": vz_info[0] if vz_info else None,
                "nearest_verizon_family_name": vz_info[1] if vz_info else None,
                "area_population_1mi": pop_info.get("pop_1mi"),
                "area_population_3mi": pop_info.get("pop_3mi"),
            })

        # 9. Sort by score descending, apply limit
        ranked_opportunities.sort(key=lambda x: x["rank_score"], reverse=True)
        ranked_opportunities = ranked_opportunities[:request.limit]

        # 10. Convert to response format with 1-based ranking
        opportunities = [
            OpportunityRanking(
                property=opp["property"],
                rank=idx + 1,
                priority_signals=opp["priority_signals"],
                signal_count=opp["signal_count"],
                nearest_corporate_store_miles=opp["nearest_corporate_store_miles"],
                nearest_retail_node_miles=opp["nearest_retail_node_miles"],
                nearest_retail_node_name=opp["nearest_retail_node_name"],
                nearest_verizon_family_miles=opp["nearest_verizon_family_miles"],
                nearest_verizon_family_name=opp["nearest_verizon_family_name"],
                area_population_1mi=opp["area_population_1mi"],
                area_population_3mi=opp["area_population_3mi"],
            )
            for idx, opp in enumerate(ranked_opportunities)
        ]

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
                "scoring": {
                    "corporate_distance": request.enable_corporate_distance_scoring,
                    "population": request.enable_population_scoring,
                    "retail_node": request.enable_retail_node_scoring,
                },
            },
            corporate_stores_in_area=corporate_store_count,
            verizon_family_stores_in_area=vz_family_store_count,
            retail_nodes_found=retail_nodes_found,
            viewport_population_center=viewport_population,
        )

    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching opportunities: {str(e)}")


@router.get("/stats")
async def get_opportunity_stats():
    """
    Get statistics about opportunity scoring and eligibility criteria.
    """
    return {
        "eligibility": {
            "category_a": {
                "name": "Vacant Land",
                "source": "ATTOM",
                "criteria": "Property type = Land, lot 0.8-2 acres, not incompatible land use",
            },
            "category_b": {
                "name": "For-Lease Listings",
                "source": "Crexi / LoopNet imports",
                "criteria": "Actively listed for lease/sale, size-filtered during import",
            },
            "category_c": {
                "name": "Vacant Retail/Office",
                "source": "ATTOM",
                "criteria": "Building 2500-6000 sqft, vacancy evidence required, not multi-tenant",
            },
        },
        "scoring": {
            "site_quality": {
                "population_density": [
                    {"condition": "12K+ within 1mi", "points": 30},
                    {"condition": "25K+ within 3mi (bonus)", "points": 10},
                    {"condition": "12K+ within 3mi only", "points": 15},
                ],
                "retail_anchor_proximity": [
                    {"condition": "Adjacent (<0.25mi)", "points": 35},
                    {"condition": "Near (<0.5mi)", "points": 25},
                    {"condition": "Within 1mi", "points": 10},
                ],
                "corporate_gap": [
                    {"condition": "7+ miles from VZ Corporate", "points": 25},
                    {"condition": "5-7 miles", "points": 20},
                    {"condition": "3-5 miles (high-pop) or 5+ (low-pop)", "points": 10},
                ],
            },
            "availability_quality": [
                {"condition": "Active for-lease listing", "points": 35},
                {"condition": "Vacant land (buildable)", "points": 25},
                {"condition": "Confirmed vacant building (signal + keyword)", "points": 20},
                {"condition": "Vacant building (signal only)", "points": 15},
            ],
            "size_fit": [
                {"condition": "Ideal lot 0.8-1.2ac", "points": 15},
                {"condition": "Acceptable lot 1.2-2.0ac", "points": 10},
                {"condition": "Ideal building 2500-3500 sqft", "points": 15},
                {"condition": "Acceptable building 3500-6000 sqft", "points": 10},
            ],
            "vz_family_colocation": [
                {"condition": "Within 0.5mi of VZ family store", "points": 10},
                {"condition": "Within 1mi", "points": 5},
            ],
            "distress_tiebreaker": [
                {"condition": "Tax delinquent or foreclosure", "points": 10},
                {"condition": "Absentee owner", "points": 5},
            ],
        },
    }
