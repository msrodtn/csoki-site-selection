from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.sql import func
from app.core.database import Base
import enum
import os


class Brand(str, enum.Enum):
    """Supported competitor brands."""
    CSOKI = "csoki"
    RUSSELL_CELLULAR = "russell_cellular"
    VERIZON_CORPORATE = "verizon_corporate"
    VICTRA = "victra"
    TMOBILE = "tmobile"
    USCELLULAR = "uscellular"


# Check if PostGIS is available
USE_POSTGIS = os.environ.get('USE_POSTGIS', 'false').lower() == 'true'

if USE_POSTGIS:
    from geoalchemy2 import Geography


class Store(Base):
    """Store/competitor location model with optional geospatial support."""

    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(50), nullable=False, index=True)

    # Address fields
    street = Column(String(255))
    city = Column(String(100), index=True)
    state = Column(String(2), index=True)
    postal_code = Column(String(10), index=True)

    # Coordinates (primary location data)
    latitude = Column(Float)
    longitude = Column(Float)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Additional fields for future use
    store_name = Column(String(255))
    phone = Column(String(20))

    __table_args__ = (
        Index('idx_stores_brand_state', 'brand', 'state'),
        Index('idx_stores_lat_lng', 'latitude', 'longitude'),
    )

    def __repr__(self):
        return f"<Store(id={self.id}, brand={self.brand}, city={self.city}, state={self.state})>"

    @property
    def full_address(self) -> str:
        """Return formatted full address."""
        parts = [self.street, self.city, self.state, self.postal_code]
        return ", ".join(filter(None, parts))


# Add PostGIS column only if enabled
if USE_POSTGIS:
    Store.location = Column(Geography(geometry_type='POINT', srid=4326))
