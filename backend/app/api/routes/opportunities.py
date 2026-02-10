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
    get_cached_attom,
    cache_attom,
)
from app.services.arcgis import fetch_demographics
from app.services.mapbox_places import fetch_mapbox_pois

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

# Verizon-family brands for co-location scoring
VERIZON_FAMILY_BRANDS = ["russell_cellular", "victra", "verizon_corporate"]

# State-level average population density (people per sq mi) for relative scoring.
# Source: US Census Bureau. Used to normalize density so rural Iowa retail hubs
# score well relative to their state, not against absolute metro thresholds.
STATE_DENSITY_BASELINES = {
    # Primary target markets
    "IA": 55.0,    # Iowa
    "NE": 25.0,    # Nebraska
    # Secondary target markets
    "NV": 28.0,    # Nevada
    "ID": 22.0,    # Idaho
    # Common surrounding states (for edge cases)
    "MN": 70.0,    # Minnesota
    "SD": 12.0,    # South Dakota
    "MO": 88.0,    # Missouri
    "WI": 108.0,   # Wisconsin
    "IL": 230.0,   # Illinois
    "KS": 36.0,    # Kansas
    "CO": 56.0,    # Colorado
    "WY": 6.0,     # Wyoming
    "MT": 8.0,     # Montana
    "UT": 40.0,    # Utah
    "OR": 44.0,    # Oregon
    "WA": 115.0,   # Washington
    # Fallback for any other state
    "_default": 90.0,
}

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
    # Residential (NOT suitable for commercial retail)
    "residential", "single family", "single-family", "multifamily", "multi-family",
    "apartment", "condominium", "condo", "townhouse", "townhome", "duplex",
    "triplex", "fourplex", "mobile home", "manufactured home", "rv park",
    "trailer park", "assisted living", "nursing home", "senior living",
    "group home", "halfway house",
    # Parks/Recreation
    "park", "playground", "recreation", "sports field", "athletic",
    "golf course", "golf ", "tennis court", "swimming pool", "skate park",
    # Agriculture
    "farm", "agricultural", "ranch", "crop", "orchard", "nursery",
    "vineyard", "greenhouse", "livestock", "dairy", "grain",
    # Infrastructure
    "railroad", "rail yard", "airport", "airstrip", "helipad",
    "cell tower", "telecommunication", "substation", "power line",
    # Environmental/Waste
    "junkyard", "scrapyard", "landfill", "dump ", "quarry", "mine ",
    "stormwater", "retention pond", "drainage", "sewage", "wastewater",
    # Waterfront/Outdoor
    "campground", "marina", "boat ramp", "fishing",
    # Advertising
    "billboard",
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
# Site-quality-first scoring (v2 — relative density, income, Goldilocks gap)
# ---------------------------------------------------------------------------

def _calculate_priority_rank(
    listing: PropertyListing,
    nearest_corporate_distance: Optional[float] = None,
    nearest_retail_node_distance: Optional[float] = None,
    nearest_vz_family_distance: Optional[float] = None,
    area_population_1mi: Optional[int] = None,
    area_population_3mi: Optional[int] = None,
    area_density_1mi: Optional[float] = None,
    area_density_3mi: Optional[float] = None,
    area_income_3mi: Optional[int] = None,
) -> tuple[int, List[str]]:
    """
    Calculate site-quality-first ranking score (v2).

    Returns (rank_score, priority_signals)
    Higher rank_score = higher priority

    Tier 1: Relative Population Density (0-35)
    Tier 2: Median Household Income (0-25)
    Tier 3: Retail Anchor Proximity (0-30)
    Tier 4: Corporate Gap — Goldilocks Zone (0-30)
    Tier 5: Availability Quality (0-20) — equalized
    Tier 6: Size Fit (0-15)
    Tier 7: VZ-Family Co-location (0-10)
    Tier 8: Distress Tiebreaker (0-15)

    Max possible: 180 pts. Practical excellent: 120+
    """
    rank_score = 0
    priority_signals = []

    signal_types = {s.signal_type for s in listing.opportunity_signals}

    # === TIER 1: RELATIVE POPULATION DENSITY (up to 35 pts) ===
    # Uses density ratio to state baseline so rural Iowa retail hubs score well

    if area_density_1mi is not None or area_density_3mi is not None:
        state = (listing.state or "").upper()
        baseline = STATE_DENSITY_BASELINES.get(state, STATE_DENSITY_BASELINES["_default"])

        density = area_density_1mi if area_density_1mi is not None else area_density_3mi
        ratio = density / baseline if baseline > 0 else 0

        density_pts = 0
        if ratio >= 50:
            density_pts = 35
            priority_signals.append(f"Urban-core density ({density:,.0f}/sqmi, {ratio:.0f}x state avg)")
        elif ratio >= 20:
            density_pts = 30
            priority_signals.append(f"High density ({density:,.0f}/sqmi, {ratio:.0f}x state avg)")
        elif ratio >= 10:
            density_pts = 25
            priority_signals.append(f"Good density ({density:,.0f}/sqmi, {ratio:.0f}x state avg)")
        elif ratio >= 5:
            density_pts = 18
            priority_signals.append(f"Moderate density ({density:,.0f}/sqmi, {ratio:.0f}x state avg)")
        elif ratio >= 2:
            density_pts = 8
            priority_signals.append(f"Low density ({density:,.0f}/sqmi, {ratio:.0f}x state avg)")

        # Bonus for strong 3mi catchment area
        if area_density_3mi is not None and area_density_1mi is not None:
            ratio_3mi = area_density_3mi / baseline if baseline > 0 else 0
            if ratio_3mi >= 10 and density_pts < 35:
                density_pts = min(density_pts + 5, 35)
                priority_signals.append(f"Strong 3mi catchment ({area_density_3mi:,.0f}/sqmi)")

        rank_score += density_pts

    # === TIER 2: MEDIAN HOUSEHOLD INCOME (up to 25 pts) ===
    # Verizon criteria: $50K+ min, $60K+ preferred

    if area_income_3mi is not None:
        income = area_income_3mi
        if income >= 80000:
            rank_score += 25
            priority_signals.append(f"Premium income area (${income:,} median HH)")
        elif income >= 70000:
            rank_score += 22
            priority_signals.append(f"Strong income (${income:,} median HH)")
        elif income >= 60000:
            rank_score += 18
            priority_signals.append(f"Good income (${income:,} median HH)")
        elif income >= 50000:
            rank_score += 12
            priority_signals.append(f"Adequate income (${income:,} median HH)")
        elif income >= 40000:
            rank_score += 5
            priority_signals.append(f"Below-target income (${income:,} median HH)")

    # === TIER 3: RETAIL ANCHOR PROXIMITY (up to 30 pts) ===
    # Continuous decay curve for better differentiation

    if nearest_retail_node_distance is not None:
        d = nearest_retail_node_distance
        if d <= 0.15:
            anchor_pts = 30
            priority_signals.append("Adjacent to major retail anchor")
        elif d <= 0.5:
            anchor_pts = round(30 - (d - 0.15) * (12 / 0.35))
            priority_signals.append(f"Near major retail anchor ({d:.2f}mi)")
        elif d <= 1.0:
            anchor_pts = round(18 - (d - 0.5) * (10 / 0.5))
            priority_signals.append(f"Retail anchor within {d:.1f}mi")
        elif d <= 1.5:
            anchor_pts = round(8 - (d - 1.0) * (6 / 0.5))
            priority_signals.append(f"Retail anchor at {d:.1f}mi")
        else:
            anchor_pts = 0
        rank_score += max(anchor_pts, 0)

    # === TIER 4: CORPORATE GAP — GOLDILOCKS ZONE (up to 30 pts) ===
    # Bell curve: 2-5mi ideal, <1.5mi too close, >12mi too far

    if nearest_corporate_distance is not None:
        d = nearest_corporate_distance

        if d >= 900:
            # No corporate store found in search area
            corp_pts = 5
            priority_signals.append("No VZ Corporate store in area (neutral)")
        elif d < 1.5:
            corp_pts = 0
            priority_signals.append(f"Too close to VZ Corporate ({d:.1f}mi)")
        elif d < 2.0:
            corp_pts = round((d - 1.5) * (15 / 0.5))
            priority_signals.append(f"Near corporate boundary ({d:.1f}mi)")
        elif d <= 5.0:
            corp_pts = 30
            priority_signals.append(f"Ideal corporate gap ({d:.1f}mi)")
        elif d <= 8.0:
            corp_pts = round(30 - (d - 5.0) * (15 / 3.0))
            priority_signals.append(f"Good corporate gap ({d:.1f}mi)")
        elif d <= 12.0:
            corp_pts = round(15 - (d - 8.0) * (10 / 4.0))
            priority_signals.append(f"Distant from corporate ({d:.1f}mi)")
        else:
            corp_pts = 3
            priority_signals.append(f"Very distant from corporate ({d:.1f}mi)")

        rank_score += max(corp_pts, 0)

    # === TIER 5: AVAILABILITY QUALITY (up to 20 pts) — EQUALIZED ===
    # All confirmed-available sources max at 20 pts (no listing auto-domination)

    if listing.source in (PropertySource.CREXI, PropertySource.LOOPNET):
        rank_score += 20
        source_label = listing.source.value.title()
        priority_signals.append(f"Active for-lease listing ({source_label})")
    elif listing.property_type == PropertyType.LAND:
        rank_score += 20
        priority_signals.append("Vacant land (buildable)")
    else:
        has_vacancy = "vacant_property" in signal_types
        has_availability = _has_availability_keywords(listing.land_use)
        if has_vacancy and has_availability:
            rank_score += 18
            priority_signals.append(f"Confirmed vacant ({listing.land_use})")
        elif has_vacancy:
            rank_score += 14
            priority_signals.append("Vacant building")
        elif has_availability:
            rank_score += 14
            priority_signals.append(f"Available ({listing.land_use})")
        else:
            rank_score += 8
            priority_signals.append("Potential availability")

    # === TIER 6: SIZE FIT (up to 15 pts) ===

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

    # === TIER 7: VZ FAMILY CO-LOCATION BONUS (up to 10 pts) ===

    if nearest_vz_family_distance is not None:
        if nearest_vz_family_distance <= 0.5:
            rank_score += 10
            priority_signals.append(f"Near VZ-family store ({nearest_vz_family_distance:.1f}mi)")
        elif nearest_vz_family_distance <= 1.0:
            rank_score += 5
            priority_signals.append(f"VZ-family store within 1mi")

    # === TIER 8: DISTRESS TIEBREAKER (up to 15 pts) ===

    if "distress" in signal_types:
        rank_score += 15
        priority_signals.append("Foreclosure/distress")
    elif "tax_delinquent" in signal_types:
        rank_score += 12
        priority_signals.append("Tax delinquent")
    elif "absentee_owner" in signal_types and "long_term_owner" in signal_types:
        rank_score += 8
        priority_signals.append("Absentee + long-term owner")
    elif "absentee_owner" in signal_types:
        rank_score += 5
        priority_signals.append("Absentee owner")
    elif "long_term_owner" in signal_types:
        rank_score += 3
        priority_signals.append("Long-term owner")

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
        description="Score based on Goldilocks distance from VZ Corporate (2-5mi ideal)"
    )
    enable_population_scoring: bool = Field(
        default=True,
        description="Score based on relative population density (vs state baseline)"
    )
    enable_retail_node_scoring: bool = Field(
        default=True,
        description="Score based on proximity to major retail anchors"
    )
    enable_income_scoring: bool = Field(
        default=True,
        description="Score based on median household income ($50K+ preferred)"
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
    area_density_1mi: Optional[float] = None
    area_income_3mi: Optional[int] = None
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
        # 1. Search ATTOM API (cached 1hr by viewport bounds)
        type_key = "|".join(sorted(pt.value for pt in property_types))
        cached_attom_props = get_cached_attom(
            request.min_lat, request.max_lat, request.min_lng, request.max_lng, type_key
        )
        if cached_attom_props is not None:
            logger.info(f"ATTOM cache hit: {len(cached_attom_props)} properties")
            attom_properties = cached_attom_props
        else:
            result: PropertySearchResult = await attom_search_bounds(
                bounds=bounds,
                property_types=property_types,
                min_opportunity_score=0,
                limit=request.limit * 2,
            )
            attom_properties = result.properties
            cache_attom(
                request.min_lat, request.max_lat, request.min_lng, request.max_lng,
                attom_properties, type_key
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
        all_properties = _merge_and_deduplicate(attom_properties, scraped_properties)

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

        # 5a-gate. Hard gate: remove properties too close to VZ Corporate (<1.0mi)
        if request.enable_corporate_distance_scoring and corporate_distances:
            pre_gate_count = len(filtered_properties)
            filtered_properties = [
                prop for prop in filtered_properties
                if corporate_distances.get(prop.id, 999.0) >= 1.0
            ]
            gate_removed = pre_gate_count - len(filtered_properties)
            if gate_removed > 0:
                logger.info(f"Corporate proximity gate removed {gate_removed} properties (<1.0mi from VZ Corporate)")

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
                        "density_1mi": demo_response.radii[0].population_density,
                        "density_3mi": demo_response.radii[1].population_density,
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
                    "density_1mi": viewport_population.get("density_1mi"),
                    "density_3mi": viewport_population.get("density_3mi"),
                    "income_3mi": viewport_population.get("income_3mi"),
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
                area_density_1mi=pop_info.get("density_1mi"),
                area_density_3mi=pop_info.get("density_3mi"),
                area_income_3mi=pop_info.get("income_3mi") if request.enable_income_scoring else None,
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
                "area_density_1mi": pop_info.get("density_1mi"),
                "area_income_3mi": pop_info.get("income_3mi"),
                "market_viability_score": rank_score,
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
                area_density_1mi=opp["area_density_1mi"],
                area_income_3mi=opp["area_income_3mi"],
                market_viability_score=opp["market_viability_score"],
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
                    "income": request.enable_income_scoring,
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
            "max_possible_score": 180,
            "tier_1_relative_density": {
                "max_points": 35,
                "description": "Population density relative to state baseline",
                "brackets": [
                    {"condition": "50x+ state avg (urban core)", "points": 35},
                    {"condition": "20x+ state avg (strong suburban)", "points": 30},
                    {"condition": "10x+ state avg (viable town center)", "points": 25},
                    {"condition": "5x+ state avg (small town commercial)", "points": 18},
                    {"condition": "2x+ state avg (borderline)", "points": 8},
                    {"condition": "Bonus: strong 3mi catchment (10x+)", "points": "+5"},
                ],
            },
            "tier_2_income": {
                "max_points": 25,
                "description": "Median household income (3mi radius)",
                "brackets": [
                    {"condition": "$80K+ (premium)", "points": 25},
                    {"condition": "$70K+ (strong)", "points": 22},
                    {"condition": "$60K+ (VZ preferred)", "points": 18},
                    {"condition": "$50K+ (VZ minimum)", "points": 12},
                    {"condition": "$40K+ (below target)", "points": 5},
                ],
            },
            "tier_3_retail_anchor": {
                "max_points": 30,
                "description": "Continuous decay from nearest retail anchor",
                "brackets": [
                    {"condition": "Adjacent (<0.15mi)", "points": 30},
                    {"condition": "Near (0.15-0.5mi)", "points": "18-30"},
                    {"condition": "Within 1mi", "points": "8-18"},
                    {"condition": "Within 1.5mi", "points": "2-8"},
                ],
            },
            "tier_4_corporate_gap_goldilocks": {
                "max_points": 30,
                "description": "Bell curve: 2-5mi ideal, <1.5mi too close, >12mi too far",
                "hard_gate": "Properties <1.0mi from VZ Corporate are removed entirely",
                "brackets": [
                    {"condition": "<1.5mi (too close)", "points": 0},
                    {"condition": "1.5-2mi (transition)", "points": "0-15"},
                    {"condition": "2-5mi (ideal zone)", "points": 30},
                    {"condition": "5-8mi (diminishing)", "points": "15-30"},
                    {"condition": "8-12mi (distant)", "points": "5-15"},
                    {"condition": ">12mi (very distant)", "points": 3},
                ],
            },
            "tier_5_availability": {
                "max_points": 20,
                "description": "Equalized — all confirmed-available sources score equally at max",
                "brackets": [
                    {"condition": "Active listing (Crexi/LoopNet)", "points": 20},
                    {"condition": "Vacant land (buildable)", "points": 20},
                    {"condition": "Confirmed vacant building", "points": 18},
                    {"condition": "Vacant building (signal only)", "points": 14},
                    {"condition": "Potential availability", "points": 8},
                ],
            },
            "tier_6_size_fit": {
                "max_points": 15,
                "brackets": [
                    {"condition": "Ideal lot 0.8-1.2ac", "points": 15},
                    {"condition": "Acceptable lot 1.2-2.0ac", "points": 10},
                    {"condition": "Ideal building 2500-3500 sqft", "points": 15},
                    {"condition": "Acceptable building 3500-6000 sqft", "points": 10},
                ],
            },
            "tier_7_vz_family_colocation": {
                "max_points": 10,
                "brackets": [
                    {"condition": "Within 0.5mi of VZ family store", "points": 10},
                    {"condition": "Within 1mi", "points": 5},
                ],
            },
            "tier_8_distress_tiebreaker": {
                "max_points": 15,
                "brackets": [
                    {"condition": "Foreclosure/distress", "points": 15},
                    {"condition": "Tax delinquent", "points": 12},
                    {"condition": "Absentee + long-term owner", "points": 8},
                    {"condition": "Absentee owner", "points": 5},
                    {"condition": "Long-term owner", "points": 3},
                ],
            },
        },
    }
