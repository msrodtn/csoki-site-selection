"""
County Property Model

Stores local county assessor data for property search as a replacement 
for the ATTOM Property API. Supports all fields needed for PropertyListing
and opportunity signal computation.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Index
from sqlalchemy.sql import func
from app.core.database import Base
import os

# Check if PostGIS is available
USE_POSTGIS = os.environ.get('USE_POSTGIS', 'false').lower() == 'true'

if USE_POSTGIS:
    from geoalchemy2 import Geography


class CountyProperty(Base):
    """
    County property record with all data needed for PropertyListing and opportunity signals.
    
    Designed to replace ATTOM Property API with local data from county assessor offices.
    """

    __tablename__ = "county_properties"

    id = Column(Integer, primary_key=True, index=True)
    
    # Source and ID tracking
    source_county = Column(String(100), nullable=False, index=True)  # e.g., "Polk County, IA"
    source_state = Column(String(2), nullable=False, index=True)     # e.g., "IA"
    parcel_id = Column(String(100), index=True)                      # County parcel/PIN identifier
    attom_id = Column(String(50), index=True)                        # ATTOM ID if available for comparison
    external_id = Column(String(100), index=True)                    # Other external ID (ReportAll, etc.)
    
    # Address and Location (required for PropertyListing)
    address = Column(String(255), index=True)
    city = Column(String(100), index=True)
    state = Column(String(2), nullable=False, index=True)
    zip_code = Column(String(10), index=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    
    # Property Classification
    property_indicator = Column(String(10), index=True)              # ATTOM-style property indicator (20, 25, 27, 50, 80)
    property_type_raw = Column(String(100))                          # Original property type from county
    land_use = Column(String(255), index=True)                       # Land use description (crucial for filtering)
    zoning = Column(String(50))                                      # Zoning classification
    
    # Property Details
    year_built = Column(Integer)
    building_sqft = Column(Float)                                    # Building square footage  
    lot_size_sqft = Column(Float)                                    # Lot size in square feet
    lot_size_acres = Column(Float, index=True)                       # Lot size in acres (computed from sqft)
    
    # Ownership (needed for absentee owner signal)
    owner_name = Column(String(255), index=True)
    owner_address_1 = Column(String(255))
    owner_address_2 = Column(String(100))
    owner_city = Column(String(100))
    owner_state = Column(String(2), index=True)                      # For absentee owner detection
    owner_zip = Column(String(10))
    owner_type = Column(String(50))                                  # individual, corporate, trust, estate, etc.
    
    # Assessment and Valuation
    assessed_value = Column(Float, index=True)                       # Current total assessed value
    assessed_land_value = Column(Float)                              # Land component
    assessed_building_value = Column(Float)                          # Building component  
    market_value = Column(Float)                                     # Market value estimate (if available)
    prior_assessed_value = Column(Float)                             # Prior year assessed value (for tax increase signal)
    assessment_year = Column(Integer)                                # Year of current assessment
    
    # Tax Information (for delinquency signals)
    tax_delinquent = Column(Boolean, default=False, index=True)      # Tax delinquent flag
    tax_amount_owed = Column(Float)                                  # Amount of delinquent taxes
    tax_year_delinquent = Column(Integer)                            # Year taxes became delinquent
    
    # Sale History (for long-term owner and pricing signals)
    last_sale_date = Column(String(10))                              # YYYY-MM-DD format
    last_sale_price = Column(Float)
    last_sale_type = Column(String(50))                              # warranty deed, quit claim, foreclosure, etc.
    
    # Distress Indicators
    foreclosure_status = Column(String(50), index=True)              # pre-foreclosure, foreclosure, etc.
    foreclosure_date = Column(String(10))                            # Date of foreclosure filing
    
    # Occupancy and Condition
    occupancy_status = Column(String(50), index=True)                # vacant, occupied, unknown
    condition_code = Column(String(20))                              # Property condition rating
    vacancy_indicator = Column(Boolean, default=False, index=True)   # Computed vacancy flag
    
    # Data Import Metadata
    import_date = Column(DateTime(timezone=True), server_default=func.now())
    import_source = Column(String(100))                              # File/system that provided this data
    import_batch_id = Column(String(100), index=True)               # Batch identifier for bulk operations
    data_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Raw Data Storage (for debugging and re-processing)
    raw_data = Column(Text)                                          # JSON string of original source data
    
    # Computed Fields (set during import/processing)
    opportunity_score = Column(Float)                                # Pre-computed opportunity score (0-100)
    opportunity_signals = Column(Text)                               # JSON array of signals found
    
    # Database indexes for common queries
    __table_args__ = (
        Index('idx_county_props_location', 'latitude', 'longitude'),
        Index('idx_county_props_source', 'source_county', 'source_state'),
        Index('idx_county_props_type_use', 'property_indicator', 'land_use'),
        Index('idx_county_props_owner_state', 'state', 'owner_state'),  # For absentee detection
        Index('idx_county_props_assessed', 'assessed_value'),
        Index('idx_county_props_lot_size', 'lot_size_acres'),
        Index('idx_county_props_distress', 'tax_delinquent', 'foreclosure_status'),
        Index('idx_county_props_import', 'import_batch_id', 'import_date'),
    )

    def __repr__(self):
        return f"<CountyProperty(id={self.id}, parcel={self.parcel_id}, address={self.address}, county={self.source_county})>"

    @property
    def full_address(self) -> str:
        """Return formatted full address."""
        parts = [self.address, self.city, self.state, self.zip_code]
        return ", ".join(filter(None, parts))
    
    @property
    def is_absentee_owner(self) -> bool:
        """Check if owner is absentee (different state than property)."""
        return (
            self.owner_state and 
            self.state and 
            self.owner_state.upper() != self.state.upper()
        )
    
    @property
    def tax_increase_percentage(self) -> float:
        """Calculate tax assessment increase percentage."""
        if not self.prior_assessed_value or self.prior_assessed_value <= 0:
            return 0.0
        if not self.assessed_value:
            return 0.0
        return ((self.assessed_value - self.prior_assessed_value) / self.prior_assessed_value) * 100
    
    @property
    def years_since_last_sale(self) -> float:
        """Calculate years since last sale."""
        if not self.last_sale_date:
            return 999.0  # Very long time if unknown
        try:
            from datetime import datetime
            sale_date = datetime.strptime(self.last_sale_date, "%Y-%m-%d")
            years = (datetime.now() - sale_date).days / 365.25
            return max(0.0, years)
        except (ValueError, TypeError):
            return 999.0


# Add PostGIS column only if enabled
if USE_POSTGIS:
    CountyProperty.location = Column(Geography(geometry_type='POINT', srid=4326))