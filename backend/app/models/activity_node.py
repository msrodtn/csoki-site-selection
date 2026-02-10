from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, Index
from sqlalchemy.sql import func
from app.core.database import Base


class ActivityNode(Base):
    """Activity node for heatmap visualization — shopping, entertainment, and dining POIs."""

    __tablename__ = "activity_nodes"

    id = Column(Integer, primary_key=True, index=True)
    osm_id = Column(BigInteger, unique=True, nullable=True)
    name = Column(String(255))
    node_category = Column(String(20), nullable=False)       # 'shopping', 'entertainment', 'dining'
    node_subcategory = Column(String(50))                     # e.g. 'big_box_super', 'movie_theater', 'qsr_major'
    weight = Column(Float, nullable=False, default=1.0)       # Heatmap contribution weight
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    state = Column(String(2))
    brand = Column(String(100))                               # Chain name if applicable
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_activity_nodes_location', 'latitude', 'longitude'),
        Index('idx_activity_nodes_category', 'node_category'),
        Index('idx_activity_nodes_state', 'state'),
        Index('idx_activity_nodes_bounds', 'node_category', 'latitude', 'longitude'),
    )

    def __repr__(self):
        return f"<ActivityNode(id={self.id}, name={self.name}, category={self.node_category}, weight={self.weight})>"
