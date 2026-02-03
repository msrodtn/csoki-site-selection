"""
Team Properties API endpoints.

CRUD operations for user-contributed property flags.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db
from app.models.team_property import TeamProperty

router = APIRouter(prefix="/team-properties", tags=["team-properties"])


# =============================================================================
# Request/Response Models
# =============================================================================

class TeamPropertyCreate(BaseModel):
    """Request model for creating a team property."""
    address: str
    city: str
    state: str
    postal_code: Optional[str] = None
    latitude: float
    longitude: float
    property_type: str = "retail"  # retail, land, office, industrial, mixed_use
    price: Optional[float] = None
    sqft: Optional[float] = None
    lot_size_acres: Optional[float] = None
    listing_url: Optional[str] = None
    source_type: Optional[str] = None  # for_sale_sign, broker, word_of_mouth, other
    notes: Optional[str] = None
    contributor_name: Optional[str] = None
    contributor_email: Optional[str] = None


class TeamPropertyUpdate(BaseModel):
    """Request model for updating a team property."""
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    property_type: Optional[str] = None
    price: Optional[float] = None
    sqft: Optional[float] = None
    lot_size_acres: Optional[float] = None
    listing_url: Optional[str] = None
    source_type: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    is_verified: Optional[bool] = None


class TeamPropertyResponse(BaseModel):
    """Response model for team property."""
    id: int
    address: str
    city: str
    state: str
    postal_code: Optional[str]
    latitude: float
    longitude: float
    property_type: str
    price: Optional[float]
    sqft: Optional[float]
    lot_size_acres: Optional[float]
    listing_url: Optional[str]
    source_type: Optional[str]
    notes: Optional[str]
    contributor_name: Optional[str]
    contributor_email: Optional[str]
    status: str
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TeamPropertyListResponse(BaseModel):
    """Response model for list of team properties."""
    total: int
    properties: List[TeamPropertyResponse]


class BoundsRequest(BaseModel):
    """Request model for bounds-based search."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float
    status: Optional[str] = None  # Filter by status


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/", response_model=TeamPropertyResponse)
def create_team_property(
    property_data: TeamPropertyCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new team-contributed property flag.

    Used when field reps spot properties with "For Sale" signs,
    get tips from brokers, or hear about opportunities.
    """
    # Create the property
    db_property = TeamProperty(
        address=property_data.address,
        city=property_data.city,
        state=property_data.state,
        postal_code=property_data.postal_code,
        latitude=property_data.latitude,
        longitude=property_data.longitude,
        property_type=property_data.property_type,
        price=property_data.price,
        sqft=property_data.sqft,
        lot_size_acres=property_data.lot_size_acres,
        listing_url=property_data.listing_url,
        source_type=property_data.source_type,
        notes=property_data.notes,
        contributor_name=property_data.contributor_name,
        contributor_email=property_data.contributor_email,
        status="active",
        is_verified=False,
    )

    db.add(db_property)
    db.commit()
    db.refresh(db_property)

    return db_property


@router.get("/", response_model=TeamPropertyListResponse)
def list_team_properties(
    status: Optional[str] = None,
    state: Optional[str] = None,
    property_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List all team-contributed properties with optional filters.
    """
    query = db.query(TeamProperty)

    if status:
        query = query.filter(TeamProperty.status == status)
    if state:
        query = query.filter(TeamProperty.state == state.upper())
    if property_type:
        query = query.filter(TeamProperty.property_type == property_type)

    total = query.count()
    properties = query.order_by(TeamProperty.created_at.desc()).offset(offset).limit(limit).all()

    return TeamPropertyListResponse(
        total=total,
        properties=properties
    )


@router.get("/{property_id}", response_model=TeamPropertyResponse)
def get_team_property(
    property_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single team property by ID.
    """
    db_property = db.query(TeamProperty).filter(TeamProperty.id == property_id).first()

    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")

    return db_property


@router.put("/{property_id}", response_model=TeamPropertyResponse)
def update_team_property(
    property_id: int,
    property_data: TeamPropertyUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a team property.

    Can be used to:
    - Update property details
    - Mark as verified
    - Change status (active, reviewed, archived, sold)
    """
    db_property = db.query(TeamProperty).filter(TeamProperty.id == property_id).first()

    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")

    # Update only provided fields
    update_data = property_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_property, field, value)

    db.commit()
    db.refresh(db_property)

    return db_property


@router.delete("/{property_id}")
def delete_team_property(
    property_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a team property.

    Consider using status='archived' instead of deleting.
    """
    db_property = db.query(TeamProperty).filter(TeamProperty.id == property_id).first()

    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")

    db.delete(db_property)
    db.commit()

    return {"message": "Property deleted successfully"}


@router.post("/in-bounds/", response_model=TeamPropertyListResponse)
def get_team_properties_in_bounds(
    bounds: BoundsRequest,
    db: Session = Depends(get_db)
):
    """
    Get team properties within map viewport bounds.

    Used to display team-flagged properties on the map.
    """
    query = db.query(TeamProperty).filter(
        and_(
            TeamProperty.latitude >= bounds.min_lat,
            TeamProperty.latitude <= bounds.max_lat,
            TeamProperty.longitude >= bounds.min_lng,
            TeamProperty.longitude <= bounds.max_lng,
        )
    )

    if bounds.status:
        query = query.filter(TeamProperty.status == bounds.status)
    else:
        # Default to active properties only
        query = query.filter(TeamProperty.status == "active")

    properties = query.all()

    return TeamPropertyListResponse(
        total=len(properties),
        properties=properties
    )
