"""
Crexi CSV Parser - Parse and filter Crexi Excel exports.

Handles the 24-column Crexi export format and applies Michael's filtering criteria:
- Category A: Empty land parcels (0.8-2 acres)
- Category B: Small buildings (2500-6000 sqft, ≤1 unit, Retail/Office)
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from app.models.scraped_listing import ScrapedListing

logger = logging.getLogger(__name__)


@dataclass
class CrexiListing:
    """Parsed Crexi listing data."""
    property_link: str
    property_name: str
    property_status: str
    property_type: str
    address: Optional[str]
    city: str
    state: str
    zip_code: Optional[str]
    tenant: Optional[str]
    lease_term: Optional[float]
    remaining_term: Optional[float]
    sqft: Optional[float]
    lot_size_acres: Optional[float]
    units: Optional[float]
    price_per_unit: Optional[float]
    noi: Optional[float]
    cap_rate: Optional[float]
    asking_price: Optional[float]
    price_per_sqft: Optional[float]
    price_per_acre: Optional[float]
    days_on_market: Optional[int]
    opportunity_zone: Optional[str]
    longitude: Optional[float]
    latitude: Optional[float]
    
    # Computed fields
    matches_criteria: bool = False
    match_category: Optional[str] = None  # "empty_land" or "small_building"


@dataclass
class ImportResult:
    """Result of importing Crexi listings to database."""
    total_parsed: int
    total_filtered: int
    total_imported: int
    total_updated: int
    total_skipped: int
    empty_land_count: int
    small_building_count: int
    location: str
    timestamp: datetime


def parse_crexi_csv(file_path: str) -> List[CrexiListing]:
    """
    Parse Crexi Excel export into structured data.
    
    Args:
        file_path: Path to the Excel file (.xlsx)
        
    Returns:
        List of parsed CrexiListing objects
        
    Raises:
        ValueError: If file format is invalid
    """
    try:
        # Read Excel file, skipping first row ("171 properties found"), using row 2 as headers
        df = pd.read_excel(file_path, header=1, skiprows=[0])
        
        # Verify expected columns
        expected_cols = [
            'Property Link', 'Property Name', 'Property Status', 'Type',
            'Address', 'City', 'State', 'Zip', 'Tenant(s)', 'Lease Term',
            'Remaining Term', 'SqFt', 'Lot Size', 'Units', 'Price/Unit',
            'NOI', 'Cap Rate', 'Asking Price', 'Price/SqFt', 'Price/Acre',
            'Days on Market', 'Opportunity Zone', 'Longitude', 'Latitude'
        ]
        
        missing_cols = [col for col in expected_cols if col not in df.columns]
        if missing_cols:
            logger.warning(f"Missing columns in Crexi export: {missing_cols}")
        
        listings = []
        
        for idx, row in df.iterrows():
            try:
                # Parse lot size (format: "2.2" or "2.2 Acres")
                lot_size = None
                if pd.notna(row.get('Lot Size')):
                    lot_str = str(row['Lot Size']).strip()
                    # Extract numeric value
                    match = re.search(r'([\d.]+)', lot_str)
                    if match:
                        lot_size = float(match.group(1))
                
                # Parse units (handle NaN)
                units = None
                if pd.notna(row.get('Units')):
                    try:
                        units = float(row['Units'])
                    except (ValueError, TypeError):
                        units = None
                
                # Create listing object
                listing = CrexiListing(
                    property_link=str(row.get('Property Link', '')).strip(),
                    property_name=str(row.get('Property Name', '')).strip(),
                    property_status=str(row.get('Property Status', '')).strip(),
                    property_type=str(row.get('Type', '')).strip(),
                    address=str(row['Address']).strip() if pd.notna(row.get('Address')) else None,
                    city=str(row.get('City', '')).strip(),
                    state=str(row.get('State', '')).strip(),
                    zip_code=str(row['Zip']).strip() if pd.notna(row.get('Zip')) else None,
                    tenant=str(row['Tenant(s)']).strip() if pd.notna(row.get('Tenant(s)')) else None,
                    lease_term=float(row['Lease Term']) if pd.notna(row.get('Lease Term')) else None,
                    remaining_term=float(row['Remaining Term']) if pd.notna(row.get('Remaining Term')) else None,
                    sqft=float(row['SqFt']) if pd.notna(row.get('SqFt')) else None,
                    lot_size_acres=lot_size,
                    units=units,
                    price_per_unit=float(row['Price/Unit']) if pd.notna(row.get('Price/Unit')) else None,
                    noi=float(row['NOI']) if pd.notna(row.get('NOI')) else None,
                    cap_rate=float(row['Cap Rate']) if pd.notna(row.get('Cap Rate')) else None,
                    asking_price=float(row['Asking Price']) if pd.notna(row.get('Asking Price')) else None,
                    price_per_sqft=float(row['Price/SqFt']) if pd.notna(row.get('Price/SqFt')) else None,
                    price_per_acre=float(row['Price/Acre']) if pd.notna(row.get('Price/Acre')) else None,
                    days_on_market=int(row['Days on Market']) if pd.notna(row.get('Days on Market')) else None,
                    opportunity_zone=str(row['Opportunity Zone']).strip() if pd.notna(row.get('Opportunity Zone')) else None,
                    longitude=float(row['Longitude']) if pd.notna(row.get('Longitude')) else None,
                    latitude=float(row['Latitude']) if pd.notna(row.get('Latitude')) else None,
                )
                
                listings.append(listing)
                
            except Exception as e:
                logger.warning(f"Error parsing row {idx}: {e}")
                continue
        
        logger.info(f"Parsed {len(listings)} listings from Crexi CSV")
        return listings
        
    except Exception as e:
        logger.error(f"Error reading Crexi CSV: {e}")
        raise ValueError(f"Failed to parse Crexi CSV: {e}")


def filter_opportunities(listings: List[CrexiListing]) -> Tuple[List[CrexiListing], dict]:
    """
    Apply Michael's criteria to filter opportunities.
    
    Criteria (OR logic):
    - Category A: Empty land parcels (0.8-2 acres, Type contains "Land")
    - Category B: Small buildings (2500-6000 sqft, ≤1 unit, Retail/Office)
    
    Args:
        listings: List of parsed Crexi listings
        
    Returns:
        Tuple of (filtered_listings, stats_dict)
    """
    empty_land = []
    small_buildings = []
    
    for listing in listings:
        # Category A: Empty Land
        if _is_empty_land(listing):
            listing.matches_criteria = True
            listing.match_category = "empty_land"
            empty_land.append(listing)
            continue
        
        # Category B: Small Buildings
        if _is_small_building(listing):
            listing.matches_criteria = True
            listing.match_category = "small_building"
            small_buildings.append(listing)
            continue
    
    filtered = empty_land + small_buildings
    
    stats = {
        "total_input": len(listings),
        "total_filtered": len(filtered),
        "empty_land_count": len(empty_land),
        "small_building_count": len(small_buildings),
        "filter_rate": f"{(len(filtered) / len(listings) * 100):.1f}%" if listings else "0%"
    }
    
    logger.info(f"Filtered {len(filtered)} opportunities from {len(listings)} listings ({stats['filter_rate']})")
    logger.info(f"  - Empty land: {len(empty_land)}")
    logger.info(f"  - Small buildings: {len(small_buildings)}")
    
    return filtered, stats


def _is_empty_land(listing: CrexiListing) -> bool:
    """Check if listing matches empty land criteria."""
    # Must have lot size
    if not listing.lot_size_acres:
        return False
    
    # Lot size: 0.8 - 2 acres
    if not (0.8 <= listing.lot_size_acres <= 2.0):
        return False
    
    # Type must contain "Land"
    if not listing.property_type or 'land' not in listing.property_type.lower():
        return False
    
    return True


def _is_small_building(listing: CrexiListing) -> bool:
    """Check if listing matches small building criteria."""
    # Must have building size
    if not listing.sqft:
        return False
    
    # Building size: 2500 - 6000 sqft
    if not (2500 <= listing.sqft <= 6000):
        return False
    
    # Units ≤ 1 (single tenant)
    if listing.units is not None and listing.units > 1:
        return False
    
    # Type must be Retail or Office (optionally Industrial)
    if not listing.property_type:
        return False
    
    prop_type_lower = listing.property_type.lower()
    valid_types = ['retail', 'office', 'industrial']
    
    if not any(t in prop_type_lower for t in valid_types):
        return False
    
    return True


def import_to_database(
    listings: List[CrexiListing],
    location: str,
    db: Session
) -> ImportResult:
    """
    Save filtered listings to scraped_listings table.
    
    Args:
        listings: List of CrexiListing objects to import
        location: Search location (e.g., "Des Moines, IA")
        db: Database session
        
    Returns:
        ImportResult with statistics
    """
    imported = 0
    updated = 0
    skipped = 0
    empty_land = 0
    small_building = 0
    
    for listing in listings:
        if not listing.matches_criteria:
            skipped += 1
            continue
        
        # Track category counts
        if listing.match_category == "empty_land":
            empty_land += 1
        elif listing.match_category == "small_building":
            small_building += 1
        
        # Extract external ID from URL
        external_id = None
        if listing.property_link:
            match = re.search(r'/properties/(\d+)/', listing.property_link)
            if match:
                external_id = match.group(1)
        
        # Check if listing already exists
        existing = None
        if external_id:
            existing = db.query(ScrapedListing).filter(
                ScrapedListing.source == "crexi",
                ScrapedListing.external_id == external_id
            ).first()
        
        # Normalize property type
        property_type = listing.property_type.lower() if listing.property_type else None
        if property_type:
            if 'retail' in property_type:
                property_type = 'retail'
            elif 'office' in property_type:
                property_type = 'office'
            elif 'industrial' in property_type:
                property_type = 'industrial'
            elif 'land' in property_type:
                property_type = 'land'
        
        # Prepare listing data
        listing_data = {
            "source": "crexi",
            "external_id": external_id,
            "listing_url": listing.property_link,
            "address": listing.address,
            "city": listing.city,
            "state": listing.state,
            "postal_code": listing.zip_code,
            "latitude": listing.latitude,
            "longitude": listing.longitude,
            "property_type": property_type,
            "price": listing.asking_price,
            "price_display": f"${listing.asking_price:,.0f}" if listing.asking_price else None,
            "sqft": listing.sqft,
            "lot_size_acres": listing.lot_size_acres,
            "title": listing.property_name,
            "description": f"{listing.property_type} - {listing.match_category.replace('_', ' ').title()}",
            "raw_data": {
                "tenant": listing.tenant,
                "lease_term": listing.lease_term,
                "remaining_term": listing.remaining_term,
                "units": listing.units,
                "price_per_unit": listing.price_per_unit,
                "noi": listing.noi,
                "cap_rate": listing.cap_rate,
                "price_per_sqft": listing.price_per_sqft,
                "price_per_acre": listing.price_per_acre,
                "days_on_market": listing.days_on_market,
                "opportunity_zone": listing.opportunity_zone,
                "match_category": listing.match_category,
                "csv_export": True
            },
            "search_city": location.split(",")[0].strip() if "," in location else location,
            "search_state": location.split(",")[1].strip() if "," in location else None,
            "is_active": True,
            "last_verified": datetime.utcnow()
        }
        
        if existing:
            # Update existing listing
            for key, value in listing_data.items():
                if value is not None:
                    setattr(existing, key, value)
            updated += 1
            logger.debug(f"Updated listing {external_id}")
        else:
            # Create new listing
            new_listing = ScrapedListing(**listing_data)
            db.add(new_listing)
            imported += 1
            logger.debug(f"Imported new listing {external_id}")
    
    # Commit all changes
    db.commit()
    
    result = ImportResult(
        total_parsed=len(listings),
        total_filtered=sum(1 for l in listings if l.matches_criteria),
        total_imported=imported,
        total_updated=updated,
        total_skipped=skipped,
        empty_land_count=empty_land,
        small_building_count=small_building,
        location=location,
        timestamp=datetime.utcnow()
    )
    
    logger.info(f"Import complete: {imported} new, {updated} updated, {skipped} skipped")
    return result
