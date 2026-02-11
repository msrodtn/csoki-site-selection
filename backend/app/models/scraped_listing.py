"""
Scraped Listing model for properties fetched via browser automation.

Stores listings scraped from external CRE platforms (Crexi, LoopNet)
using authenticated browser sessions with user credentials.
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class ScrapedListing(Base):
    """
    A property listing scraped from an external CRE platform.

    These are active listings fetched from Crexi, LoopNet, etc. using
    the user's own authenticated credentials for internal business use.
    """
    __tablename__ = "scraped_listings"

    id = Column(Integer, primary_key=True, index=True)

    # Source tracking
    source = Column(String(50), nullable=False, index=True)  # 'crexi', 'loopnet'
    external_id = Column(String(100), index=True)  # Platform's listing ID
    listing_url = Column(String(500))

    # Location
    address = Column(String(255))
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(2), nullable=False, index=True)
    postal_code = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)

    # Property details
    property_type = Column(String(50), index=True)  # retail, land, office, industrial, mixed_use
    price = Column(Float)
    price_display = Column(String(50))  # "$1.2M", "Contact for Pricing"
    sqft = Column(Float)
    lot_size_acres = Column(Float)
    year_built = Column(Integer)

    # Transaction type
    transaction_type = Column(String(20), nullable=True, index=True)  # "sale", "lease", or None

    # Listing details
    title = Column(String(500))
    description = Column(Text)
    broker_name = Column(String(200))
    broker_company = Column(String(200))
    broker_phone = Column(String(50))
    broker_email = Column(String(255))

    # Additional data (JSON for flexibility)
    raw_data = Column(JSON)  # Store original scraped data
    images = Column(JSON)  # List of image URLs

    # Search context (what search produced this result)
    search_city = Column(String(100))  # The city searched
    search_state = Column(String(2))  # The state searched
    search_radius_miles = Column(Float)

    # Status
    is_active = Column(Boolean, default=True)
    last_verified = Column(DateTime)  # When we last confirmed it's still active

    # Timestamps
    scraped_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    def __repr__(self):
        return f"<ScrapedListing {self.id}: {self.source} - {self.address or self.title}>"
