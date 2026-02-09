"""
Opportunity Feedback API routes.

Dev-facing endpoints for submitting ground-truth feedback on opportunity sites
and analyzing patterns to refine the scoring algorithm.
"""

import json
import logging
from typing import Optional, List
from collections import Counter

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.opportunity_feedback import OpportunityFeedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


# --- Request / Response Models ---

class FeedbackCreate(BaseModel):
    attom_id: Optional[str] = None
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: float
    longitude: float
    rating: str  # "good", "bad", "maybe"
    feedback: Optional[str] = None

    # Scoring snapshot
    rank_score: Optional[float] = None
    priority_signals: Optional[List[str]] = None
    property_type: Optional[str] = None
    land_use: Optional[str] = None
    sqft: Optional[float] = None
    lot_size_acres: Optional[float] = None
    assessed_value: Optional[float] = None
    year_built: Optional[int] = None

    # Market context
    nearest_corporate_store_miles: Optional[float] = None
    area_population_1mi: Optional[int] = None
    market_viability_score: Optional[float] = None


class FeedbackResponse(BaseModel):
    id: int
    attom_id: Optional[str]
    address: str
    city: Optional[str]
    state: Optional[str]
    latitude: float
    longitude: float
    rating: str
    feedback: Optional[str]
    rank_score: Optional[float]
    priority_signals: Optional[List[str]]
    property_type: Optional[str]
    land_use: Optional[str]
    sqft: Optional[float]
    lot_size_acres: Optional[float]
    assessed_value: Optional[float]
    year_built: Optional[int]
    nearest_corporate_store_miles: Optional[float]
    area_population_1mi: Optional[int]
    market_viability_score: Optional[float]
    created_at: Optional[str]

    class Config:
        from_attributes = True


def _row_to_response(row: OpportunityFeedback) -> FeedbackResponse:
    """Convert a DB row to a response model."""
    signals = None
    if row.priority_signals:
        try:
            signals = json.loads(row.priority_signals)
        except (json.JSONDecodeError, TypeError):
            signals = [row.priority_signals]

    return FeedbackResponse(
        id=row.id,
        attom_id=row.attom_id,
        address=row.address,
        city=row.city,
        state=row.state,
        latitude=row.latitude,
        longitude=row.longitude,
        rating=row.rating,
        feedback=row.feedback,
        rank_score=row.rank_score,
        priority_signals=signals,
        property_type=row.property_type,
        land_use=row.land_use,
        sqft=row.sqft,
        lot_size_acres=row.lot_size_acres,
        assessed_value=row.assessed_value,
        year_built=row.year_built,
        nearest_corporate_store_miles=row.nearest_corporate_store_miles,
        area_population_1mi=row.area_population_1mi,
        market_viability_score=row.market_viability_score,
        created_at=str(row.created_at) if row.created_at else None,
    )


# --- Endpoints ---

@router.post("/", response_model=FeedbackResponse)
def submit_feedback(body: FeedbackCreate, db: Session = Depends(get_db)):
    """Submit feedback for an opportunity site."""
    if body.rating not in ("good", "bad", "maybe"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="rating must be 'good', 'bad', or 'maybe'")

    row = OpportunityFeedback(
        attom_id=body.attom_id,
        address=body.address,
        city=body.city,
        state=body.state,
        latitude=body.latitude,
        longitude=body.longitude,
        rating=body.rating,
        feedback=body.feedback,
        rank_score=body.rank_score,
        priority_signals=json.dumps(body.priority_signals) if body.priority_signals else None,
        property_type=body.property_type,
        land_use=body.land_use,
        sqft=body.sqft,
        lot_size_acres=body.lot_size_acres,
        assessed_value=body.assessed_value,
        year_built=body.year_built,
        nearest_corporate_store_miles=body.nearest_corporate_store_miles,
        area_population_1mi=body.area_population_1mi,
        market_viability_score=body.market_viability_score,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(f"Feedback #{row.id}: {row.rating} for {row.address}")
    return _row_to_response(row)


@router.get("/", response_model=List[FeedbackResponse])
def list_feedback(
    rating: Optional[str] = Query(None, description="Filter by rating: good, bad, maybe"),
    state: Optional[str] = Query(None, description="Filter by state (2-letter code)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List feedback entries with optional filters."""
    query = db.query(OpportunityFeedback)
    if rating:
        query = query.filter(OpportunityFeedback.rating == rating)
    if state:
        query = query.filter(OpportunityFeedback.state == state.upper())
    rows = query.order_by(OpportunityFeedback.created_at.desc()).offset(offset).limit(limit).all()
    return [_row_to_response(r) for r in rows]


@router.get("/analysis")
def feedback_analysis(db: Session = Depends(get_db)):
    """Aggregate feedback patterns for scoring algorithm tuning."""
    rows = db.query(OpportunityFeedback).all()

    if not rows:
        return {"total_entries": 0, "message": "No feedback entries yet."}

    # Group by rating
    by_rating: dict[str, list] = {}
    for r in rows:
        by_rating.setdefault(r.rating, []).append(r)

    # Rating counts
    rating_counts = {k: len(v) for k, v in by_rating.items()}

    # Average rank_score by rating
    avg_score: dict[str, Optional[float]] = {}
    for rating, entries in by_rating.items():
        scores = [e.rank_score for e in entries if e.rank_score is not None]
        avg_score[rating] = round(sum(scores) / len(scores), 1) if scores else None

    # Common priority signals by rating
    def _top_signals(entries: list, n: int = 10) -> list:
        counter: Counter = Counter()
        for e in entries:
            if e.priority_signals:
                try:
                    signals = json.loads(e.priority_signals)
                    counter.update(signals)
                except (json.JSONDecodeError, TypeError):
                    pass
        return counter.most_common(n)

    signals_by_rating = {k: _top_signals(v) for k, v in by_rating.items()}

    # Land use breakdown by rating
    land_use_by_rating: dict[str, dict] = {}
    for rating, entries in by_rating.items():
        counter: Counter = Counter()
        for e in entries:
            counter[e.land_use or "(none)"] += 1
        land_use_by_rating[rating] = dict(counter.most_common(10))

    # Property type breakdown by rating
    prop_type_by_rating: dict[str, dict] = {}
    for rating, entries in by_rating.items():
        counter: Counter = Counter()
        for e in entries:
            counter[e.property_type or "(unknown)"] += 1
        prop_type_by_rating[rating] = dict(counter.most_common(10))

    return {
        "total_entries": len(rows),
        "by_rating": rating_counts,
        "avg_rank_score_by_rating": avg_score,
        "common_signals_by_rating": signals_by_rating,
        "land_use_by_rating": land_use_by_rating,
        "property_type_by_rating": prop_type_by_rating,
    }
