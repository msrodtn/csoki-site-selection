from sqlalchemy import Column, Integer, String, Float, DateTime, Index, Enum as SQLEnum
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from app.core.database import Base
import enum


class Brand(str, enum.Enum):
    """Supported competitor brands."""
    CSOKI = "csoki"
    RUSSELL_CELLULAR = "russell_cellular"
    VERIZON_CORPORATE = "verizon_corporate"
    VICTRA = "victra"
    TMOBILE = "tmobile"
    USCELLULAR = "uscellular"


class Store(Base):
    """Store/competitor location model with geospatial support."""

    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(50), nullable=False, index=True)

    # Address fields
    street = Column(String(255))
    city = Column(String(100), index=True)
    state = Column(String(2), index=True)
    postal_code = Column(String(10), index=True)

    # Geospatial - PostGIS geography point (SRID 4326 = WGS84)
    location = Column(Geography(geometry_type='POINT', srid=4326))

    # Coordinates (also stored separately for easy access)
    latitude = Column(Float)
    longitude = Column(Float)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Additional fields for future use
    store_name = Column(String(255))
    phone = Column(String(20))

    __table_args__ = (
        # Note: GeoAlchemy2 creates spatial index automatically for Geography columns
        Index('idx_stores_brand_state', 'brand', 'state'),
    )

    def __repr__(self):
        return f"<Store(id={self.id}, brand={self.brand}, city={self.city}, state={self.state})>"

    @property
    def full_address(self) -> str:
        """Return formatted full address."""
        parts = [self.street, self.city, self.state, self.postal_code]
        return ", ".join(filter(None, parts))
