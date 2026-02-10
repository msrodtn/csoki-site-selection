"""
Activity Nodes API — serves pre-cached POI data for the Activity Node Heat Map.

Returns shopping, entertainment, and dining POIs within map viewport bounds
for heatmap visualization of foot traffic potential.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_db
from app.models.activity_node import ActivityNode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/activity-nodes", tags=["activity-nodes"])


class ActivityNodeBoundsRequest(BaseModel):
    min_lat: float = Field(..., description="Southern boundary latitude")
    max_lat: float = Field(..., description="Northern boundary latitude")
    min_lng: float = Field(..., description="Western boundary longitude")
    max_lng: float = Field(..., description="Eastern boundary longitude")
    categories: Optional[List[str]] = Field(None, description="Filter by node categories: shopping, entertainment, dining")


class ActivityNodeItem(BaseModel):
    id: int
    name: Optional[str]
    node_category: str
    node_subcategory: Optional[str]
    weight: float
    latitude: float
    longitude: float
    brand: Optional[str]

    class Config:
        from_attributes = True


class ActivityNodeBoundsResponse(BaseModel):
    total: int
    nodes: List[ActivityNodeItem]


@router.post("/within-bounds/", response_model=ActivityNodeBoundsResponse)
async def get_activity_nodes_in_bounds(
    request: ActivityNodeBoundsRequest,
    db: Session = Depends(get_db),
):
    """Return activity nodes within map viewport bounds for heatmap rendering."""
    query = db.query(ActivityNode).filter(
        and_(
            ActivityNode.latitude >= request.min_lat,
            ActivityNode.latitude <= request.max_lat,
            ActivityNode.longitude >= request.min_lng,
            ActivityNode.longitude <= request.max_lng,
        )
    )

    if request.categories:
        query = query.filter(ActivityNode.node_category.in_(request.categories))

    # Cap at 5000 to prevent overloading the browser
    nodes = query.limit(5000).all()

    logger.info(
        f"Activity nodes: {len(nodes)} found in bounds "
        f"({request.min_lat:.2f},{request.min_lng:.2f})-({request.max_lat:.2f},{request.max_lng:.2f})"
    )

    return ActivityNodeBoundsResponse(
        total=len(nodes),
        nodes=[ActivityNodeItem.model_validate(n) for n in nodes],
    )


@router.get("/stats/")
async def get_activity_node_stats(db: Session = Depends(get_db)):
    """Return summary statistics about imported activity nodes."""
    from sqlalchemy import func

    results = (
        db.query(
            ActivityNode.node_category,
            ActivityNode.state,
            func.count(ActivityNode.id),
        )
        .group_by(ActivityNode.node_category, ActivityNode.state)
        .all()
    )

    stats = {}
    total = 0
    for cat, state, count in results:
        if cat not in stats:
            stats[cat] = {"total": 0, "by_state": {}}
        stats[cat]["total"] += count
        stats[cat]["by_state"][state] = count
        total += count

    return {"total": total, "by_category": stats}
