"""
Team Property model for user-contributed property flags.

Allows field reps and team members to flag properties they've spotted
that may not appear in ATTOM data (e.g., "For Sale" signs, broker contacts).
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean
from sqlalchemy.sql import func

from app.core.database import Base


class TeamProperty(Base):
    """
    A property flagged by a team member.

    These are user-contributed properties that complement ATTOM data:
    - Properties with "For Sale" signs spotted in the field
    - Tips from broker contacts
    - Word of mouth leads
    - Properties not yet listed online
    """
    __tablename__ = "team_properties"

    id = Column(Integer, primary_key=True, index=True)

    # Location (required)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)
    postal_code = Column(String(10))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Property details (optional)
    property_type = Column(String(50), default='retail')  # retail, land, office, industrial, mixed_use
    price = Column(Float)  # Asking price if known
    sqft = Column(Float)  # Square footage if known
    lot_size_acres = Column(Float)  # Lot size if known

    # Source information
    listing_url = Column(String(500))  # Link to external listing (LoopNet, Crexi, etc.)
    source_type = Column(String(50))  # 'for_sale_sign', 'broker', 'word_of_mouth', 'other'
    notes = Column(Text)  # Free-form notes about why this is an opportunity

    # Contributor info
    contributor_name = Column(String(100))
    contributor_email = Column(String(255))

    # Status tracking
    status = Column(String(50), default='active')  # active, reviewed, archived, sold
    is_verified = Column(Boolean, default=False)  # Has someone verified this lead?

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    def __repr__(self):
        return f"<TeamProperty {self.id}: {self.address}, {self.city}, {self.state}>"
