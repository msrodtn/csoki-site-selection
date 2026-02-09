"""
Opportunity Feedback model for iterative scoring refinement.

Dev-facing ground-truth data: captures human judgment (good/bad/maybe) alongside
a snapshot of the algorithm's scoring output so we can analyze mismatches and
tune scoring weights over time.
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class OpportunityFeedback(Base):
    __tablename__ = "opportunity_feedback"

    id = Column(Integer, primary_key=True, index=True)

    # Property identification (snapshot — not a FK since ATTOM IDs are ephemeral)
    attom_id = Column(String(50))
    address = Column(String(255), nullable=False)
    city = Column(String(100))
    state = Column(String(2), index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Feedback
    rating = Column(String(20), nullable=False, index=True)  # "good", "bad", "maybe"
    feedback = Column(Text)  # Free-form explanation of why

    # Scoring snapshot (captured at time of feedback)
    rank_score = Column(Float)
    priority_signals = Column(Text)  # JSON array of signal strings
    property_type = Column(String(50))  # retail, land, office, etc.
    land_use = Column(String(200))  # ATTOM propLandUse value
    sqft = Column(Float)
    lot_size_acres = Column(Float)
    assessed_value = Column(Float)
    year_built = Column(Integer)

    # Market context snapshot
    nearest_corporate_store_miles = Column(Float)
    area_population_1mi = Column(Integer)
    market_viability_score = Column(Float)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    def __repr__(self):
        return f"<OpportunityFeedback {self.id}: {self.rating} — {self.address}>"
