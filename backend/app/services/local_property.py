"""
Local Property Data Service

Drop-in replacement for ATTOM Property API service using local PostGIS database.
Provides identical interface to attom.py but queries county_properties table
instead of external ATTOM API.

Supports:
- Property search by geographic bounds and radius
- All 12+ opportunity signal calculations
- Property type classification
- PostGIS spatial queries for performance
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
import json
import math
import logging

# Import models and types from attom.py to maintain compatibility
from .attom import (
    PropertyListing,
    PropertySearchResult, 
    PropertyType,
    PropertySource,
    OpportunitySignal,
    GeoBounds,
    _classify_property_type,
    _format_price,
)

from ..models.county_property import CountyProperty
from ..core.database import SessionLocal
import os

logger = logging.getLogger(__name__)

# Check if PostGIS is available
USE_POSTGIS = os.environ.get('USE_POSTGIS', 'false').lower() == 'true'


def _calculate_opportunity_signals_local(prop: CountyProperty) -> tuple[List[OpportunitySignal], float]:
    """
    Calculate opportunity signals and score based on local county property data.
    
    Replicates the logic from attom._calculate_opportunity_signals() but uses
    local database fields instead of ATTOM API response structure.
    
    Returns (signals_list, opportunity_score)
    """
    signals = []
    score = 0.0

    logger.debug(f"[Local Signal Calc] Processing property {prop.parcel_id} at {prop.address}")

    # ========== HIGH-VALUE SIGNALS ==========

    # Check for tax delinquency
    if prop.tax_delinquent:
        signals.append(OpportunitySignal(
            signal_type="tax_delinquent",
            description="Property has delinquent taxes",
            strength="high"
        ))
        score += 25
        if prop.tax_amount_owed:
            # Update description with amount if available
            signals[-1].description = f"Tax delinquent (${prop.tax_amount_owed:,.0f} owed)"

    # Check for foreclosure/distress status
    if prop.foreclosure_status:
        signals.append(OpportunitySignal(
            signal_type="distress",
            description=f"Foreclosure status: {prop.foreclosure_status}",
            strength="high"
        ))
        score += 30

    # ========== MEDIUM-VALUE SIGNALS ==========

    # Check ownership duration (long-term owners may be more willing to sell)
    years_owned = prop.years_since_last_sale
    if years_owned < 900 and years_owned > 20:  # 900 = unknown/very old
        signals.append(OpportunitySignal(
            signal_type="long_term_owner",
            description=f"Same owner for {int(years_owned)}+ years",
            strength="low"
        ))
        score += 8

    # Check for corporate vs individual ownership (estates, trusts = opportunity)
    if prop.owner_type:
        owner_type_lower = prop.owner_type.lower()
        if "trust" in owner_type_lower or "estate" in owner_type_lower:
            signals.append(OpportunitySignal(
                signal_type="estate_ownership",
                description="Owned by trust or estate",
                strength="medium"
            ))
            score += 20

    # Check assessed vs market value gap
    if prop.assessed_value and prop.market_value and prop.market_value > 0:
        ratio = prop.assessed_value / prop.market_value
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
    if prop.lot_size_acres:
        if prop.lot_size_acres >= 2.0:
            signals.append(OpportunitySignal(
                signal_type="large_lot",
                description=f"Large lot: {prop.lot_size_acres:.2f} acres",
                strength="medium"
            ))
            score += 10
        elif prop.lot_size_acres >= 1.0:
            signals.append(OpportunitySignal(
                signal_type="sizeable_lot",
                description=f"Lot size: {prop.lot_size_acres:.2f} acres",
                strength="low"
            ))
            score += 5

    # ========== ENHANCED SIGNALS ==========

    # Check building age
    if prop.year_built:
        try:
            building_age = datetime.now().year - int(prop.year_built)
            if building_age >= 50:
                signals.append(OpportunitySignal(
                    signal_type="aging_building",
                    description=f"Built {prop.year_built} ({building_age} years old)",
                    strength="low"
                ))
                score += 8
        except (ValueError, TypeError):
            pass

    # Check for absentee owner (out-of-state = less attachment, higher likelihood to sell)
    if prop.is_absentee_owner:
        signals.append(OpportunitySignal(
            signal_type="absentee_owner",
            description=f"Out-of-state owner ({prop.owner_state})",
            strength="medium"
        ))
        score += 12

    # Check for recent tax increases (financial pressure indicator)
    tax_increase = prop.tax_increase_percentage
    if tax_increase > 20:  # More than 20% increase
        signals.append(OpportunitySignal(
            signal_type="tax_pressure",
            description=f"Tax assessment increased {tax_increase:.0f}% recently",
            strength="medium"
        ))
        score += 12
    elif tax_increase > 10:  # 10-20% increase
        signals.append(OpportunitySignal(
            signal_type="rising_taxes",
            description=f"Tax assessment up {tax_increase:.0f}%",
            strength="low"
        ))
        score += 5

    # Check for vacant/unoccupied status
    if prop.vacancy_indicator or (prop.occupancy_status and "vacant" in prop.occupancy_status.lower()):
        signals.append(OpportunitySignal(
            signal_type="vacant_property",
            description="Property appears vacant",
            strength="high"
        ))
        score += 20

    # Multiple parcels indicator (if we track this in future)
    # Note: Not implemented in current schema but placeholder for future enhancement

    # Cap score at 100
    score = min(score, 100)

    logger.debug(f"[Local Signal Calc] Generated {len(signals)} signals with score {score:.1f} for {prop.parcel_id}")

    return signals, score


def _convert_county_property_to_listing(prop: CountyProperty) -> PropertyListing:
    """
    Convert CountyProperty database record to PropertyListing object.
    
    Maps all local database fields to the standard PropertyListing format
    used throughout the application.
    """
    
    # Classify property type using same logic as ATTOM service
    property_type = _classify_property_type(
        prop_indicator=prop.property_indicator,
        prop_type=prop.property_type_raw,
        land_use=prop.land_use
    )
    
    # Calculate opportunity signals from local data
    signals, opp_score = _calculate_opportunity_signals_local(prop)
    
    # Use assessed or market value as price estimate
    price = prop.market_value or prop.assessed_value
    
    # Generate unique ID
    property_id = f"local_{prop.source_state}_{prop.id}"
    
    return PropertyListing(
        id=property_id,
        address=prop.address or f"{prop.latitude:.4f}, {prop.longitude:.4f}",
        city=prop.city or "",
        state=prop.state or "",
        zip_code=prop.zip_code,
        latitude=prop.latitude,
        longitude=prop.longitude,
        property_type=property_type,
        price=price,
        price_display=_format_price(price),
        sqft=prop.building_sqft,
        lot_size_acres=prop.lot_size_acres,
        year_built=prop.year_built,
        owner_name=prop.owner_name,
        owner_type=prop.owner_type,
        assessed_value=prop.assessed_value,
        market_value=prop.market_value,
        last_sale_date=prop.last_sale_date,
        last_sale_price=prop.last_sale_price,
        source=PropertySource.LOCAL,
        listing_type="opportunity",  # Local data provides opportunity data like ATTOM
        opportunity_signals=signals,
        opportunity_score=opp_score,
        land_use=prop.land_use,
        raw_data=json.loads(prop.raw_data) if prop.raw_data else None,
    )


async def search_properties_by_bounds(
    bounds: GeoBounds,
    property_types: Optional[List[PropertyType]] = None,
    min_opportunity_score: float = 0,
    limit: int = 50,
) -> PropertySearchResult:
    """
    Search for properties within geographic bounds using local PostGIS database.
    
    This function provides identical interface to attom.search_properties_by_bounds()
    but queries the local county_properties table instead of ATTOM API.
    """
    
    # Calculate center point for response
    center_lat = (bounds.min_lat + bounds.max_lat) / 2
    center_lng = (bounds.min_lng + bounds.max_lng) / 2
    
    # Calculate approximate radius for response metadata
    lat_diff = bounds.max_lat - bounds.min_lat
    lng_diff = bounds.max_lng - bounds.min_lng
    lat_miles = lat_diff * 69
    lng_miles = lng_diff * 69 * math.cos(math.radians(center_lat))
    approx_radius = max(lat_miles, lng_miles) / 2
    
    db = SessionLocal()
    try:
        # Build base query
        query = db.query(CountyProperty).filter(
            CountyProperty.latitude >= bounds.min_lat,
            CountyProperty.latitude <= bounds.max_lat,
            CountyProperty.longitude >= bounds.min_lng,
            CountyProperty.longitude <= bounds.max_lng,
        )
        
        # Filter by property types if specified
        if property_types:
            # Map PropertyType enum to property indicators and land use patterns
            type_filters = []
            
            for prop_type in property_types:
                if prop_type == PropertyType.RETAIL:
                    type_filters.append(CountyProperty.property_indicator == '25')
                elif prop_type == PropertyType.OFFICE:
                    type_filters.append(CountyProperty.property_indicator == '27')
                elif prop_type == PropertyType.INDUSTRIAL:
                    type_filters.append(CountyProperty.property_indicator.in_(['50', '51', '52']))
                elif prop_type == PropertyType.LAND:
                    type_filters.append(CountyProperty.property_indicator == '80')
                elif prop_type == PropertyType.MIXED_USE:
                    type_filters.append(CountyProperty.property_indicator == '20')
            
            if type_filters:
                query = query.filter(or_(*type_filters))
        
        # Apply opportunity score filter
        if min_opportunity_score > 0:
            # For properties without pre-computed scores, we'll compute on the fly
            # In production, you'd want to pre-compute these for performance
            query = query.filter(
                or_(
                    CountyProperty.opportunity_score >= min_opportunity_score,
                    CountyProperty.opportunity_score.is_(None)  # Include unscored for computation
                )
            )
        
        # Order by opportunity potential (highest first)
        # Priority: tax delinquent > foreclosure > vacant > absentee owner > assessed value desc
        query = query.order_by(
            CountyProperty.tax_delinquent.desc(),
            CountyProperty.foreclosure_status.desc(),
            CountyProperty.vacancy_indicator.desc(),
            CountyProperty.assessed_value.desc()
        )
        
        # Apply limit with some buffer for filtering
        raw_results = query.limit(limit * 2).all()
        
        logger.info(f"[Local Search] Found {len(raw_results)} raw properties in bounds")
        
        # Convert to PropertyListing objects
        properties = []
        for prop in raw_results:
            try:
                listing = _convert_county_property_to_listing(prop)
                
                # Apply opportunity score filter after conversion (for dynamic scoring)
                if listing.opportunity_score and listing.opportunity_score >= min_opportunity_score:
                    properties.append(listing)
                elif not listing.opportunity_score and min_opportunity_score == 0:
                    properties.append(listing)
                
                # Stop when we have enough results
                if len(properties) >= limit:
                    break
                    
            except Exception as e:
                logger.error(f"[Local Search] Error converting property {prop.id}: {e}")
                continue
        
        # Sort by opportunity score (highest first)
        properties.sort(key=lambda p: p.opportunity_score or 0, reverse=True)
        
        logger.info(f"[Local Search] Returning {len(properties)} properties after filtering")
        
        return PropertySearchResult(
            center_latitude=center_lat,
            center_longitude=center_lng,
            radius_miles=approx_radius,
            properties=properties,
            total_found=len(properties),
            sources=["LOCAL"],
            search_timestamp=datetime.now().isoformat(),
        )
        
    except Exception as e:
        logger.error(f"[Local Search] Database error: {e}")
        raise ValueError(f"Local property search failed: {e}")
    finally:
        db.close()


async def search_properties_by_radius(
    latitude: float,
    longitude: float,
    radius_miles: float = 5.0,
    property_types: Optional[List[PropertyType]] = None,
    min_opportunity_score: float = 0,
    limit: int = 50,
) -> PropertySearchResult:
    """
    Search for properties within a radius of a point using local PostGIS database.
    
    This function provides identical interface to attom.search_properties_by_radius()
    but uses PostGIS spatial queries for better performance.
    """
    
    db = SessionLocal()
    try:
        if USE_POSTGIS:
            # Use PostGIS for precise distance calculations
            # ST_DWithin uses meters, so convert miles to meters
            radius_meters = radius_miles * 1609.34
            
            # Create point from input coordinates  
            point_wkt = f"POINT({longitude} {latitude})"
            
            query = db.query(CountyProperty).filter(
                text("ST_DWithin(location, ST_GeomFromText(:point, 4326), :radius)").params(
                    point=point_wkt,
                    radius=radius_meters
                )
            )
            
        else:
            # Fall back to bounding box approximation
            # 1 degree latitude ≈ 69 miles
            lat_delta = radius_miles / 69.0
            lng_delta = radius_miles / (69.0 * math.cos(math.radians(latitude)))
            
            query = db.query(CountyProperty).filter(
                CountyProperty.latitude >= latitude - lat_delta,
                CountyProperty.latitude <= latitude + lat_delta,
                CountyProperty.longitude >= longitude - lng_delta,
                CountyProperty.longitude <= longitude + lng_delta,
            )
        
        # Apply same filtering logic as bounds search
        if property_types:
            type_filters = []
            for prop_type in property_types:
                if prop_type == PropertyType.RETAIL:
                    type_filters.append(CountyProperty.property_indicator == '25')
                elif prop_type == PropertyType.OFFICE:
                    type_filters.append(CountyProperty.property_indicator == '27')
                elif prop_type == PropertyType.INDUSTRIAL:
                    type_filters.append(CountyProperty.property_indicator.in_(['50', '51', '52']))
                elif prop_type == PropertyType.LAND:
                    type_filters.append(CountyProperty.property_indicator == '80')
                elif prop_type == PropertyType.MIXED_USE:
                    type_filters.append(CountyProperty.property_indicator == '20')
            
            if type_filters:
                query = query.filter(or_(*type_filters))
        
        if min_opportunity_score > 0:
            query = query.filter(
                or_(
                    CountyProperty.opportunity_score >= min_opportunity_score,
                    CountyProperty.opportunity_score.is_(None)
                )
            )
        
        # Order by opportunity indicators
        query = query.order_by(
            CountyProperty.tax_delinquent.desc(),
            CountyProperty.foreclosure_status.desc(),
            CountyProperty.vacancy_indicator.desc(),
            CountyProperty.assessed_value.desc()
        )
        
        raw_results = query.limit(limit * 2).all()
        
        logger.info(f"[Local Radius Search] Found {len(raw_results)} raw properties within {radius_miles}mi")
        
        # Convert and filter
        properties = []
        for prop in raw_results:
            try:
                listing = _convert_county_property_to_listing(prop)
                
                # Additional distance filter for non-PostGIS mode
                if not USE_POSTGIS:
                    # Haversine distance check
                    from ..utils.geo import haversine
                    distance = haversine(longitude, latitude, prop.longitude, prop.latitude)
                    if distance > radius_miles:
                        continue
                
                if listing.opportunity_score and listing.opportunity_score >= min_opportunity_score:
                    properties.append(listing)
                elif not listing.opportunity_score and min_opportunity_score == 0:
                    properties.append(listing)
                
                if len(properties) >= limit:
                    break
                    
            except Exception as e:
                logger.error(f"[Local Radius Search] Error converting property {prop.id}: {e}")
                continue
        
        properties.sort(key=lambda p: p.opportunity_score or 0, reverse=True)
        
        logger.info(f"[Local Radius Search] Returning {len(properties)} properties")
        
        return PropertySearchResult(
            center_latitude=latitude,
            center_longitude=longitude,
            radius_miles=radius_miles,
            properties=properties,
            total_found=len(properties),
            sources=["LOCAL"],
            search_timestamp=datetime.now().isoformat(),
        )
        
    except Exception as e:
        logger.error(f"[Local Radius Search] Database error: {e}")
        raise ValueError(f"Local radius search failed: {e}")
    finally:
        db.close()


def get_property_details(property_id: str) -> Optional[PropertyListing]:
    """
    Get detailed information for a specific property by local ID.
    
    Provides interface compatibility with attom.get_property_details().
    """
    
    # Parse local property ID format: "local_{state}_{db_id}"
    try:
        if not property_id.startswith("local_"):
            return None
        
        parts = property_id.split("_")
        if len(parts) < 3:
            return None
            
        db_id = int(parts[2])
        
    except (ValueError, IndexError):
        logger.error(f"[Local Details] Invalid property ID format: {property_id}")
        return None
    
    db = SessionLocal()
    try:
        prop = db.query(CountyProperty).filter(CountyProperty.id == db_id).first()
        
        if not prop:
            logger.warning(f"[Local Details] Property not found: {property_id}")
            return None
            
        return _convert_county_property_to_listing(prop)
        
    except Exception as e:
        logger.error(f"[Local Details] Database error for {property_id}: {e}")
        return None
    finally:
        db.close()


def check_local_data_availability() -> Dict[str, Any]:
    """
    Check local database status and data availability.
    
    Similar to attom.check_attom_api_key() but for local data health.
    """
    
    db = SessionLocal()
    try:
        # Test database connection and count records
        total_count = db.query(CountyProperty).count()
        
        # Count by state/county
        state_counts = db.query(
            CountyProperty.source_state,
            CountyProperty.source_county
        ).distinct().all()
        
        # Count recent imports  
        recent_cutoff = datetime.now() - timedelta(days=30)
        recent_count = db.query(CountyProperty).filter(
            CountyProperty.import_date >= recent_cutoff
        ).count()
        
        # Check PostGIS availability
        postgis_available = USE_POSTGIS
        if USE_POSTGIS:
            try:
                db.execute(text("SELECT PostGIS_Version();"))
                postgis_version = True
            except Exception:
                postgis_version = False
        else:
            postgis_version = False
        
        return {
            "configured": True,
            "healthy": total_count > 0,
            "message": f"Local database has {total_count:,} properties",
            "total_properties": total_count,
            "coverage": {
                "states_counties": len(state_counts),
                "jurisdictions": [f"{county}, {state}" for state, county in state_counts[:10]]  # Sample
            },
            "recent_imports": recent_count,
            "postgis_enabled": USE_POSTGIS,
            "postgis_available": postgis_version,
            "last_checked": datetime.now().isoformat(),
        }
        
    except Exception as e:
        return {
            "configured": True,
            "healthy": False,
            "message": f"Local database error: {str(e)}",
            "error": str(e),
            "last_checked": datetime.now().isoformat(),
        }
    finally:
        db.close()