"""
County Data Import Service

Bulk import utilities for loading county assessor data into the county_properties table.
Supports common formats from Iowa, Nebraska, and other state assessor offices.

Features:
- CSV/Excel file parsing
- Shapefile support (with geometry extraction)
- Geocoding fallback for missing coordinates
- Data deduplication and validation
- Batch processing for large datasets
- Configurable field mapping for different county formats
"""

import csv
import json
import logging
import pandas as pd
import hashlib
from typing import Optional, List, Dict, Any, Union, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text

# Geocoding
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import time
import requests

# GIS support (optional)
try:
    import geopandas as gpd
    import fiona
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

from ..models.county_property import CountyProperty
from ..core.database import SessionLocal
from ..core.config import settings
import os

logger = logging.getLogger(__name__)

# Check PostGIS availability
USE_POSTGIS = os.environ.get('USE_POSTGIS', 'false').lower() == 'true'


@dataclass
class ImportStats:
    """Statistics from a data import operation."""
    total_records: int = 0
    processed_records: int = 0
    imported_records: int = 0
    skipped_records: int = 0
    error_records: int = 0
    duplicate_records: int = 0
    geocoded_records: int = 0
    batch_id: str = ""
    start_time: datetime = None
    end_time: datetime = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass 
class FieldMapping:
    """Configuration for mapping source data fields to CountyProperty fields."""
    
    # Core identification
    parcel_id: Optional[str] = None
    external_id: Optional[str] = None
    
    # Address/location
    address: Optional[str] = None
    street_number: Optional[str] = None
    street_name: Optional[str] = None
    city: Optional[str] = None  
    state: Optional[str] = None
    zip_code: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    
    # Property details
    property_type: Optional[str] = None
    property_indicator: Optional[str] = None
    land_use: Optional[str] = None
    zoning: Optional[str] = None
    year_built: Optional[str] = None
    building_sqft: Optional[str] = None
    lot_size_sqft: Optional[str] = None
    lot_size_acres: Optional[str] = None
    
    # Ownership
    owner_name: Optional[str] = None
    owner_address: Optional[str] = None
    owner_city: Optional[str] = None
    owner_state: Optional[str] = None
    owner_zip: Optional[str] = None
    owner_type: Optional[str] = None
    
    # Assessment/valuation
    assessed_value: Optional[str] = None
    assessed_land_value: Optional[str] = None
    assessed_building_value: Optional[str] = None
    market_value: Optional[str] = None
    prior_assessed_value: Optional[str] = None
    assessment_year: Optional[str] = None
    
    # Tax information
    tax_delinquent: Optional[str] = None
    tax_amount_owed: Optional[str] = None
    tax_year_delinquent: Optional[str] = None
    
    # Sale history
    last_sale_date: Optional[str] = None
    last_sale_price: Optional[str] = None
    last_sale_type: Optional[str] = None
    
    # Distress indicators
    foreclosure_status: Optional[str] = None
    foreclosure_date: Optional[str] = None
    
    # Occupancy
    occupancy_status: Optional[str] = None
    condition_code: Optional[str] = None
    vacancy_indicator: Optional[str] = None


# Predefined field mappings for common county formats
IOWA_STANDARD_MAPPING = FieldMapping(
    parcel_id="PARCEL_ID",
    address="PROP_ADDR", 
    city="PROP_CITY",
    state="PROP_STATE",
    zip_code="PROP_ZIP",
    latitude="LATITUDE",
    longitude="LONGITUDE",
    owner_name="OWNER_NAME",
    owner_address="MAIL_ADDR",
    owner_city="MAIL_CITY", 
    owner_state="MAIL_STATE",
    owner_zip="MAIL_ZIP",
    assessed_value="TOTAL_VALUE",
    assessed_land_value="LAND_VALUE",
    assessed_building_value="BLDG_VALUE",
    land_use="LAND_USE_DESC",
    year_built="YEAR_BUILT",
    building_sqft="BLDG_SF",
    lot_size_acres="ACRES",
    last_sale_date="SALE_DATE",
    last_sale_price="SALE_PRICE"
)

NEBRASKA_CAMA_MAPPING = FieldMapping(
    parcel_id="PIN",
    address="SITUS_ADDR",
    city="SITUS_CITY", 
    state="SITUS_STATE",
    zip_code="SITUS_ZIP",
    latitude="Y_COORD",
    longitude="X_COORD",
    owner_name="OWNER",
    owner_address="OWNER_ADDR",
    owner_city="OWNER_CITY",
    owner_state="OWNER_STATE", 
    owner_zip="OWNER_ZIP",
    assessed_value="APPRAISED_VAL",
    land_use="USE_CODE_DESC",
    year_built="YR_BLT",
    building_sqft="GLA",
    lot_size_sqft="LOT_SIZE"
)

# Generic mapping for when column names are unclear
GENERIC_MAPPING = FieldMapping(
    # Will attempt to auto-detect common variations
)


class CountyDataImporter:
    """Main class for importing county assessor data."""
    
    def __init__(
        self, 
        county_name: str,
        state_code: str,
        field_mapping: Optional[FieldMapping] = None,
        source_description: Optional[str] = None
    ):
        """
        Initialize importer for a specific county.
        
        Args:
            county_name: Full county name (e.g., "Polk County")
            state_code: Two-letter state code (e.g., "IA")
            field_mapping: Custom field mapping, or None to auto-detect
            source_description: Description of data source for metadata
        """
        self.county_name = county_name
        self.state_code = state_code.upper()
        self.field_mapping = field_mapping or GENERIC_MAPPING
        self.source_description = source_description or f"{county_name}, {state_code} Assessor"
        
        # Generate unique batch ID for this import
        self.batch_id = self._generate_batch_id()
        
        # Setup geocoder
        self.geocoder = Nominatim(
            user_agent=settings.GEOCODING_USER_AGENT,
            timeout=10
        )
        self.geocoding_cache = {}
        
        logger.info(f"[County Import] Initialized for {county_name}, {state_code} (batch: {self.batch_id})")
    
    
    def _generate_batch_id(self) -> str:
        """Generate unique batch identifier for this import run."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        county_hash = hashlib.md5(f"{self.county_name}_{self.state_code}".encode()).hexdigest()[:8]
        return f"{self.state_code}_{county_hash}_{timestamp}"
    
    
    def import_csv(
        self, 
        file_path: Union[str, Path],
        encoding: str = 'utf-8',
        delimiter: str = ',',
        skip_rows: int = 0,
        max_records: Optional[int] = None,
        dry_run: bool = False
    ) -> ImportStats:
        """
        Import data from CSV file.
        
        Args:
            file_path: Path to CSV file
            encoding: File encoding (utf-8, latin-1, etc.)
            delimiter: CSV delimiter character
            skip_rows: Number of header rows to skip
            max_records: Maximum records to process (for testing)
            dry_run: If True, validate but don't insert into database
            
        Returns:
            ImportStats object with operation results
        """
        
        stats = ImportStats(
            batch_id=self.batch_id,
            start_time=datetime.now()
        )
        
        file_path = Path(file_path)
        if not file_path.exists():
            stats.errors.append(f"File not found: {file_path}")
            return stats
        
        logger.info(f"[County Import] Starting CSV import from {file_path}")
        
        try:
            # Read CSV with pandas for better handling of large files
            df = pd.read_csv(
                file_path, 
                encoding=encoding,
                delimiter=delimiter,
                skiprows=skip_rows,
                low_memory=False,
                na_values=['', 'NULL', 'null', 'N/A', 'NA']
            )
            
            if max_records:
                df = df.head(max_records)
            
            stats.total_records = len(df)
            logger.info(f"[County Import] Loaded {stats.total_records} records from CSV")
            
            # Auto-detect field mapping if not provided
            if self.field_mapping == GENERIC_MAPPING:
                self.field_mapping = self._auto_detect_mapping(df.columns.tolist())
            
            # Process records
            db = SessionLocal()
            try:
                for idx, row in df.iterrows():
                    try:
                        property_record = self._parse_row(row, stats)
                        
                        if property_record and not dry_run:
                            # Check for duplicates
                            existing = self._find_duplicate(db, property_record)
                            if existing:
                                stats.duplicate_records += 1
                                logger.debug(f"[County Import] Skipping duplicate parcel {property_record.parcel_id}")
                                continue
                            
                            # Insert record
                            db.add(property_record)
                            stats.imported_records += 1
                            
                            # Commit in batches for performance
                            if stats.imported_records % 1000 == 0:
                                db.commit()
                                logger.info(f"[County Import] Committed {stats.imported_records} records")
                        
                        elif property_record:
                            # Dry run - just count successful parses
                            stats.imported_records += 1
                        
                        stats.processed_records += 1
                        
                    except Exception as e:
                        stats.error_records += 1
                        stats.errors.append(f"Row {idx}: {str(e)}")
                        if len(stats.errors) < 100:  # Limit error collection
                            logger.warning(f"[County Import] Error processing row {idx}: {e}")
                
                # Final commit
                if not dry_run:
                    db.commit()
                    
            finally:
                db.close()
            
        except Exception as e:
            stats.errors.append(f"CSV import failed: {str(e)}")
            logger.error(f"[County Import] CSV import failed: {e}")
        
        stats.end_time = datetime.now()
        
        logger.info(
            f"[County Import] CSV import complete: "
            f"{stats.imported_records}/{stats.total_records} imported, "
            f"{stats.duplicate_records} duplicates, "
            f"{stats.error_records} errors, "
            f"{stats.geocoded_records} geocoded"
        )
        
        return stats
    
    
    def import_shapefile(
        self,
        file_path: Union[str, Path],
        max_records: Optional[int] = None,
        dry_run: bool = False
    ) -> ImportStats:
        """
        Import data from Shapefile (requires geopandas).
        
        Extracts coordinates from geometry if lat/lng fields are missing.
        """
        
        stats = ImportStats(
            batch_id=self.batch_id,
            start_time=datetime.now()
        )
        
        if not GEOPANDAS_AVAILABLE:
            stats.errors.append("Shapefile import requires geopandas (pip install geopandas)")
            return stats
        
        file_path = Path(file_path)
        if not file_path.exists():
            stats.errors.append(f"Shapefile not found: {file_path}")
            return stats
        
        logger.info(f"[County Import] Starting shapefile import from {file_path}")
        
        try:
            # Read shapefile
            gdf = gpd.read_file(file_path)
            
            # Convert to WGS84 if needed
            if gdf.crs != 'EPSG:4326':
                logger.info(f"[County Import] Reprojecting from {gdf.crs} to WGS84")
                gdf = gdf.to_crs('EPSG:4326')
            
            # Extract centroids for point coordinates
            gdf['centroid'] = gdf.geometry.centroid
            gdf['latitude'] = gdf.centroid.y
            gdf['longitude'] = gdf.centroid.x
            
            if max_records:
                gdf = gdf.head(max_records)
                
            stats.total_records = len(gdf)
            logger.info(f"[County Import] Loaded {stats.total_records} features from shapefile")
            
            # Auto-detect field mapping
            if self.field_mapping == GENERIC_MAPPING:
                self.field_mapping = self._auto_detect_mapping(gdf.columns.tolist())
            
            # Process features
            db = SessionLocal()
            try:
                for idx, row in gdf.iterrows():
                    try:
                        # Use extracted coordinates if mapping fields are missing
                        if not self.field_mapping.latitude and 'latitude' in row:
                            row['LATITUDE'] = row['latitude']
                        if not self.field_mapping.longitude and 'longitude' in row:
                            row['LONGITUDE'] = row['longitude']
                        
                        property_record = self._parse_row(row, stats)
                        
                        if property_record and not dry_run:
                            existing = self._find_duplicate(db, property_record)
                            if existing:
                                stats.duplicate_records += 1
                                continue
                                
                            db.add(property_record)
                            stats.imported_records += 1
                            
                            if stats.imported_records % 1000 == 0:
                                db.commit()
                                logger.info(f"[County Import] Committed {stats.imported_records} records")
                        
                        elif property_record:
                            stats.imported_records += 1
                            
                        stats.processed_records += 1
                        
                    except Exception as e:
                        stats.error_records += 1
                        stats.errors.append(f"Feature {idx}: {str(e)}")
                        if len(stats.errors) < 100:
                            logger.warning(f"[County Import] Error processing feature {idx}: {e}")
                
                if not dry_run:
                    db.commit()
                    
            finally:
                db.close()
            
        except Exception as e:
            stats.errors.append(f"Shapefile import failed: {str(e)}")
            logger.error(f"[County Import] Shapefile import failed: {e}")
        
        stats.end_time = datetime.now()
        
        logger.info(
            f"[County Import] Shapefile import complete: "
            f"{stats.imported_records}/{stats.total_records} imported"
        )
        
        return stats
    
    
    def _auto_detect_mapping(self, column_names: List[str]) -> FieldMapping:
        """
        Auto-detect field mapping from column names.
        
        Looks for common patterns in county assessor data.
        """
        
        columns_lower = [col.lower() for col in column_names]
        mapping = FieldMapping()
        
        # Common patterns for auto-detection
        patterns = {
            'parcel_id': ['parcel', 'pin', 'parcel_id', 'parcel_number', 'account'],
            'address': ['address', 'situs', 'prop_addr', 'property_address', 'street'],
            'city': ['city', 'prop_city', 'situs_city'],
            'state': ['state', 'prop_state', 'situs_state'],
            'zip_code': ['zip', 'zipcode', 'postal', 'prop_zip'],
            'latitude': ['lat', 'latitude', 'y_coord', 'y'],
            'longitude': ['lon', 'lng', 'longitude', 'x_coord', 'x'],
            'owner_name': ['owner', 'owner_name', 'owner1'],
            'owner_city': ['owner_city', 'mail_city'],
            'owner_state': ['owner_state', 'mail_state'],
            'assessed_value': ['assessed', 'total_value', 'appraised', 'market'],
            'land_use': ['land_use', 'use_code', 'use_desc', 'prop_type'],
            'year_built': ['year_built', 'yr_built', 'built'],
            'building_sqft': ['sqft', 'square_feet', 'building_sf', 'bldg_sf', 'gla'],
            'lot_size_acres': ['acres', 'acreage', 'lot_acres']
        }
        
        for field, pattern_list in patterns.items():
            for pattern in pattern_list:
                for i, col_lower in enumerate(columns_lower):
                    if pattern in col_lower:
                        setattr(mapping, field, column_names[i])
                        logger.debug(f"[County Import] Auto-detected {field} -> {column_names[i]}")
                        break
                if getattr(mapping, field):
                    break
        
        return mapping
    
    
    def _parse_row(self, row: pd.Series, stats: ImportStats) -> Optional[CountyProperty]:
        """
        Parse a single row of data into CountyProperty object.
        
        Handles data type conversion, validation, and geocoding fallback.
        """
        
        try:
            # Extract basic fields using mapping
            record_data = {}
            
            # Helper function to safely extract field
            def get_field(mapping_field: str, default=None):
                field_name = getattr(self.field_mapping, mapping_field)
                if field_name and field_name in row and pd.notna(row[field_name]):
                    return str(row[field_name]).strip()
                return default
            
            # Core identification
            parcel_id = get_field('parcel_id')
            if not parcel_id:
                logger.debug("[County Import] Skipping row with no parcel ID")
                return None
            
            # Address components
            address = get_field('address')
            street_num = get_field('street_number', '')
            street_name = get_field('street_name', '')
            
            # Build full address if components are separate
            if not address and (street_num or street_name):
                address = f"{street_num} {street_name}".strip()
            
            city = get_field('city')
            state = get_field('state', self.state_code)
            zip_code = get_field('zip_code')
            
            # Coordinates
            lat_str = get_field('latitude')
            lng_str = get_field('longitude') 
            
            latitude, longitude = self._parse_coordinates(lat_str, lng_str, address, city, state, stats)
            
            if not latitude or not longitude:
                logger.debug(f"[County Import] Skipping {parcel_id} - no valid coordinates")
                stats.skipped_records += 1
                return None
            
            # Property details
            property_type = get_field('property_type')
            property_indicator = self._classify_property_indicator(
                get_field('property_indicator'), 
                property_type,
                get_field('land_use')
            )
            
            land_use = get_field('land_use')
            zoning = get_field('zoning')
            
            # Numeric fields with safe conversion
            year_built = self._safe_int(get_field('year_built'))
            building_sqft = self._safe_float(get_field('building_sqft'))
            lot_size_sqft = self._safe_float(get_field('lot_size_sqft'))
            lot_size_acres = self._safe_float(get_field('lot_size_acres'))
            
            # Convert sqft to acres if only sqft available
            if not lot_size_acres and lot_size_sqft:
                lot_size_acres = lot_size_sqft / 43560
            
            # Ownership
            owner_name = get_field('owner_name')
            owner_city = get_field('owner_city')
            owner_state = get_field('owner_state')
            owner_type = self._classify_owner_type(owner_name)
            
            # Valuation
            assessed_value = self._safe_float(get_field('assessed_value'))
            assessed_land_value = self._safe_float(get_field('assessed_land_value'))
            assessed_building_value = self._safe_float(get_field('assessed_building_value'))
            market_value = self._safe_float(get_field('market_value'))
            prior_assessed_value = self._safe_float(get_field('prior_assessed_value'))
            
            # Tax information
            tax_delinquent = self._safe_bool(get_field('tax_delinquent'))
            tax_amount_owed = self._safe_float(get_field('tax_amount_owed'))
            
            # Sale information
            last_sale_date = self._parse_date(get_field('last_sale_date'))
            last_sale_price = self._safe_float(get_field('last_sale_price'))
            
            # Occupancy indicators
            occupancy_status = get_field('occupancy_status')
            vacancy_indicator = self._detect_vacancy(occupancy_status, land_use, property_type)
            
            # Create record
            property_record = CountyProperty(
                source_county=self.county_name,
                source_state=self.state_code,
                parcel_id=parcel_id,
                external_id=get_field('external_id'),
                
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                latitude=latitude,
                longitude=longitude,
                
                property_indicator=property_indicator,
                property_type_raw=property_type,
                land_use=land_use,
                zoning=zoning,
                
                year_built=year_built,
                building_sqft=building_sqft,
                lot_size_sqft=lot_size_sqft,
                lot_size_acres=lot_size_acres,
                
                owner_name=owner_name,
                owner_address_1=get_field('owner_address'),
                owner_city=owner_city,
                owner_state=owner_state,
                owner_zip=get_field('owner_zip'),
                owner_type=owner_type,
                
                assessed_value=assessed_value,
                assessed_land_value=assessed_land_value,
                assessed_building_value=assessed_building_value,
                market_value=market_value,
                prior_assessed_value=prior_assessed_value,
                assessment_year=self._safe_int(get_field('assessment_year')),
                
                tax_delinquent=tax_delinquent,
                tax_amount_owed=tax_amount_owed,
                tax_year_delinquent=self._safe_int(get_field('tax_year_delinquent')),
                
                last_sale_date=last_sale_date,
                last_sale_price=last_sale_price,
                last_sale_type=get_field('last_sale_type'),
                
                foreclosure_status=get_field('foreclosure_status'),
                foreclosure_date=self._parse_date(get_field('foreclosure_date')),
                
                occupancy_status=occupancy_status,
                condition_code=get_field('condition_code'),
                vacancy_indicator=vacancy_indicator,
                
                import_source=self.source_description,
                import_batch_id=self.batch_id,
                raw_data=json.dumps(row.to_dict(), default=str) if len(row) < 50 else None  # Limit raw data size
            )
            
            # Add PostGIS location if enabled
            if USE_POSTGIS:
                # Will be set via SQL trigger or post-processing
                pass
            
            return property_record
            
        except Exception as e:
            logger.error(f"[County Import] Error parsing row for parcel {parcel_id}: {e}")
            raise
    
    
    def _parse_coordinates(
        self, 
        lat_str: Optional[str], 
        lng_str: Optional[str],
        address: Optional[str],
        city: Optional[str], 
        state: Optional[str],
        stats: ImportStats
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Parse and validate coordinates, with geocoding fallback.
        """
        
        # Try direct coordinate parsing first
        try:
            if lat_str and lng_str:
                latitude = float(lat_str)
                longitude = float(lng_str) 
                
                # Basic validation
                if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                    return latitude, longitude
        except (ValueError, TypeError):
            pass
        
        # Geocoding fallback if coordinates missing/invalid
        if address and city and state:
            full_address = f"{address}, {city}, {state}"
            
            # Check cache first
            if full_address in self.geocoding_cache:
                cached = self.geocoding_cache[full_address]
                return cached['lat'], cached['lng']
            
            try:
                # Rate limit geocoding
                time.sleep(1.0 / settings.GEOCODING_RATE_LIMIT)
                
                location = self.geocoder.geocode(full_address)
                if location:
                    lat, lng = location.latitude, location.longitude
                    
                    # Cache result
                    self.geocoding_cache[full_address] = {'lat': lat, 'lng': lng}
                    stats.geocoded_records += 1
                    
                    logger.debug(f"[County Import] Geocoded: {full_address} -> {lat}, {lng}")
                    return lat, lng
                    
            except (GeocoderTimedOut, GeocoderUnavailable) as e:
                logger.warning(f"[County Import] Geocoding failed for {full_address}: {e}")
            
        return None, None
    
    
    def _classify_property_indicator(
        self, 
        indicator: Optional[str],
        prop_type: Optional[str], 
        land_use: Optional[str]
    ) -> Optional[str]:
        """
        Convert property type/land use to ATTOM-style property indicator.
        
        ATTOM indicators:
        - 20 = Commercial (general)  
        - 25 = Retail
        - 27 = Office Building
        - 50 = Industrial
        - 80 = Vacant Land
        """
        
        if indicator and indicator.isdigit():
            return indicator
        
        # Combine all available text for classification
        combined = f"{prop_type or ''} {land_use or ''}".lower()
        
        if not combined.strip():
            return "20"  # Default commercial
        
        # Land indicators
        if any(x in combined for x in ['vacant', 'land', 'undeveloped', 'agricultural']):
            return "80"
        
        # Retail indicators  
        if any(x in combined for x in ['retail', 'store', 'shop', 'restaurant', 'commercial']):
            return "25"
        
        # Office indicators
        if any(x in combined for x in ['office', 'professional']):
            return "27"
        
        # Industrial indicators
        if any(x in combined for x in ['industrial', 'warehouse', 'manufacturing']):
            return "50"
        
        return "20"  # Default commercial
    
    
    def _classify_owner_type(self, owner_name: Optional[str]) -> Optional[str]:
        """Classify owner type based on name patterns."""
        if not owner_name:
            return None
        
        name_lower = owner_name.lower()
        
        if any(x in name_lower for x in ['trust', 'trustee']):
            return "trust"
        if any(x in name_lower for x in ['estate', 'heir']):
            return "estate"
        if any(x in name_lower for x in ['llc', 'inc', 'corp', 'company', 'ltd']):
            return "corporate"
        
        return "individual"
    
    
    def _detect_vacancy(
        self, 
        occupancy: Optional[str], 
        land_use: Optional[str],
        prop_type: Optional[str]
    ) -> bool:
        """Detect vacancy indicators from available fields."""
        
        combined = f"{occupancy or ''} {land_use or ''} {prop_type or ''}".lower()
        
        vacancy_terms = ['vacant', 'empty', 'unoccupied', 'abandoned', 'closed']
        return any(term in combined for term in vacancy_terms)
    
    
    def _find_duplicate(self, db: Session, record: CountyProperty) -> Optional[CountyProperty]:
        """Check for existing duplicate records."""
        
        # Check by parcel ID first (most reliable)
        if record.parcel_id:
            existing = db.query(CountyProperty).filter(
                CountyProperty.source_county == record.source_county,
                CountyProperty.parcel_id == record.parcel_id
            ).first()
            
            if existing:
                return existing
        
        # Check by coordinates (within 50m)
        if record.latitude and record.longitude:
            lat_tolerance = 0.0005  # ~50m
            lng_tolerance = 0.0005
            
            existing = db.query(CountyProperty).filter(
                CountyProperty.source_county == record.source_county,
                CountyProperty.latitude.between(
                    record.latitude - lat_tolerance,
                    record.latitude + lat_tolerance
                ),
                CountyProperty.longitude.between(
                    record.longitude - lng_tolerance, 
                    record.longitude + lng_tolerance
                )
            ).first()
            
            if existing:
                return existing
        
        return None
    
    
    def _safe_int(self, value: Optional[str]) -> Optional[int]:
        """Safely convert string to integer."""
        if not value:
            return None
        try:
            return int(float(str(value)))  # Handle "1000.0" format
        except (ValueError, TypeError):
            return None
    
    
    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        """Safely convert string to float."""
        if not value:
            return None
        try:
            # Handle currency formatting
            clean_value = str(value).replace('$', '').replace(',', '')
            return float(clean_value)
        except (ValueError, TypeError):
            return None
    
    
    def _safe_bool(self, value: Optional[str]) -> bool:
        """Safely convert string to boolean.""" 
        if not value:
            return False
        
        value_str = str(value).lower().strip()
        return value_str in ['true', '1', 'yes', 'y', 'delinquent', 'active']
    
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse date string and return YYYY-MM-DD format."""
        if not date_str:
            return None
        
        try:
            # Try common date formats
            from dateutil import parser
            parsed = parser.parse(str(date_str))
            return parsed.strftime('%Y-%m-%d')
        except Exception:
            return None


def create_importer_for_county(county_name: str, state_code: str) -> CountyDataImporter:
    """
    Factory function to create importer with appropriate field mapping.
    
    Attempts to use predefined mappings for known counties/states.
    """
    
    state_upper = state_code.upper()
    county_lower = county_name.lower()
    
    # Use state-specific mappings when available
    if state_upper == "IA":
        mapping = IOWA_STANDARD_MAPPING
    elif state_upper == "NE":
        mapping = NEBRASKA_CAMA_MAPPING
    else:
        mapping = GENERIC_MAPPING
    
    return CountyDataImporter(
        county_name=county_name,
        state_code=state_code,
        field_mapping=mapping,
        source_description=f"{county_name}, {state_code} County Assessor"
    )


def bulk_import_directory(
    directory_path: Union[str, Path],
    file_pattern: str = "*.csv",
    county_state_mapping: Optional[Dict[str, Tuple[str, str]]] = None,
    dry_run: bool = False
) -> List[ImportStats]:
    """
    Bulk import all files matching pattern from a directory.
    
    Args:
        directory_path: Directory containing data files
        file_pattern: Glob pattern for files to process
        county_state_mapping: Dict mapping filename -> (county, state)
        dry_run: Validate without importing
        
    Returns:
        List of ImportStats for each file processed
    """
    
    directory = Path(directory_path)
    if not directory.exists():
        raise ValueError(f"Directory not found: {directory}")
    
    files = list(directory.glob(file_pattern))
    if not files:
        logger.warning(f"No files found matching {file_pattern} in {directory}")
        return []
    
    results = []
    
    for file_path in files:
        logger.info(f"[Bulk Import] Processing {file_path.name}")
        
        # Determine county/state from mapping or filename
        if county_state_mapping and file_path.name in county_state_mapping:
            county, state = county_state_mapping[file_path.name]
        else:
            # Try to parse from filename (e.g., "polk_county_ia.csv")
            name_parts = file_path.stem.lower().split('_')
            if len(name_parts) >= 2:
                county = " ".join(name_parts[:-1]).title() + " County"  
                state = name_parts[-1].upper()
            else:
                logger.error(f"[Bulk Import] Cannot determine county/state for {file_path.name}")
                continue
        
        try:
            importer = create_importer_for_county(county, state)
            
            if file_path.suffix.lower() == '.csv':
                stats = importer.import_csv(file_path, dry_run=dry_run)
            elif file_path.suffix.lower() in ['.shp', '.geojson']:
                stats = importer.import_shapefile(file_path, dry_run=dry_run)
            else:
                logger.warning(f"[Bulk Import] Unsupported file type: {file_path}")
                continue
            
            results.append(stats)
            
        except Exception as e:
            logger.error(f"[Bulk Import] Failed to process {file_path.name}: {e}")
            # Create error stats
            error_stats = ImportStats(
                batch_id="error",
                start_time=datetime.now(),
                end_time=datetime.now()
            )
            error_stats.errors.append(f"Import failed: {str(e)}")
            results.append(error_stats)
    
    # Summary log
    total_imported = sum(s.imported_records for s in results)
    total_errors = sum(s.error_records for s in results)
    
    logger.info(
        f"[Bulk Import] Complete: {len(files)} files, "
        f"{total_imported} records imported, "
        f"{total_errors} errors"
    )
    
    return results