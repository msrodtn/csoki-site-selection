from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import Optional
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.models.store import Store, Brand

router = APIRouter(prefix="/locations", tags=["locations"])


# Pydantic schemas
class StoreResponse(BaseModel):
    id: int
    brand: str
    street: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]

    class Config:
        from_attributes = True


class StoreListResponse(BaseModel):
    total: int
    stores: list[StoreResponse]


class BoundsRequest(BaseModel):
    north: float = Field(..., ge=-90, le=90)
    south: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)
    west: float = Field(..., ge=-180, le=180)
    brands: Optional[list[str]] = None


class RadiusRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_miles: float = Field(default=10, ge=0.1, le=100)
    brands: Optional[list[str]] = None


class StoreStats(BaseModel):
    brand: str
    count: int
    states: list[str]


class NearestCompetitorRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class NearestCompetitor(BaseModel):
    brand: str
    distance_miles: float
    store: StoreResponse


class NearestCompetitorsResponse(BaseModel):
    latitude: float
    longitude: float
    competitors: list[NearestCompetitor]


@router.get("/", response_model=StoreListResponse)
def get_all_locations(
    db: Session = Depends(get_db),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    state: Optional[str] = Query(None, description="Filter by state (2-letter code)"),
    city: Optional[str] = Query(None, description="Filter by city"),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    """Get all store locations with optional filters."""
    query = db.query(Store)

    if brand:
        query = query.filter(Store.brand == brand.lower())
    if state:
        query = query.filter(Store.state == state.upper())
    if city:
        query = query.filter(Store.city.ilike(f"%{city}%"))

    total = query.count()
    stores = query.offset(offset).limit(limit).all()

    return StoreListResponse(total=total, stores=stores)


@router.get("/brands", response_model=list[str])
def get_brands(db: Session = Depends(get_db)):
    """Get list of all brands in the database."""
    result = db.query(Store.brand).distinct().all()
    return [r[0] for r in result]


@router.get("/stats", response_model=list[StoreStats])
def get_stats(db: Session = Depends(get_db)):
    """Get store count statistics by brand."""
    stats = []
    brands = db.query(Store.brand).distinct().all()

    for (brand,) in brands:
        count = db.query(Store).filter(Store.brand == brand).count()
        states = db.query(Store.state).filter(Store.brand == brand).distinct().all()
        stats.append(StoreStats(
            brand=brand,
            count=count,
            states=sorted([s[0] for s in states if s[0]])
        ))

    return sorted(stats, key=lambda x: x.count, reverse=True)


@router.get("/state/{state}", response_model=StoreListResponse)
def get_locations_by_state(
    state: str,
    db: Session = Depends(get_db),
    brand: Optional[str] = Query(None),
):
    """Get all stores in a specific state."""
    query = db.query(Store).filter(Store.state == state.upper())

    if brand:
        query = query.filter(Store.brand == brand.lower())

    stores = query.all()
    return StoreListResponse(total=len(stores), stores=stores)


@router.post("/within-bounds", response_model=StoreListResponse)
def get_locations_within_bounds(
    bounds: BoundsRequest,
    db: Session = Depends(get_db),
):
    """Get stores within map viewport bounds."""
    query = db.query(Store).filter(
        Store.latitude.isnot(None),
        Store.longitude.isnot(None),
        Store.latitude >= bounds.south,
        Store.latitude <= bounds.north,
        Store.longitude >= bounds.west,
        Store.longitude <= bounds.east,
    )

    if bounds.brands:
        query = query.filter(Store.brand.in_([b.lower() for b in bounds.brands]))

    stores = query.all()
    return StoreListResponse(total=len(stores), stores=stores)


@router.post("/within-radius", response_model=StoreListResponse)
def get_locations_within_radius(
    request: RadiusRequest,
    db: Session = Depends(get_db),
):
    """Get stores within a radius (in miles) of a point."""
    # Convert miles to meters (1 mile = 1609.34 meters)
    radius_meters = request.radius_miles * 1609.34

    # Use PostGIS ST_DWithin for efficient radius query
    point = func.ST_SetSRID(
        func.ST_MakePoint(request.longitude, request.latitude),
        4326
    )

    query = db.query(Store).filter(
        Store.location.isnot(None),
        func.ST_DWithin(
            Store.location,
            point,
            radius_meters
        )
    )

    if request.brands:
        query = query.filter(Store.brand.in_([b.lower() for b in request.brands]))

    # Order by distance
    query = query.order_by(
        func.ST_Distance(Store.location, point)
    )

    stores = query.all()
    return StoreListResponse(total=len(stores), stores=stores)


@router.post("/nearest-competitors", response_model=NearestCompetitorsResponse)
def get_nearest_competitors(
    request: NearestCompetitorRequest,
    db: Session = Depends(get_db),
):
    """Get the nearest store of each brand from a given point."""
    # Create point for distance calculation
    point = func.ST_SetSRID(
        func.ST_MakePoint(request.longitude, request.latitude),
        4326
    )

    # Get all unique brands
    brands = db.query(Store.brand).distinct().all()
    brands = [b[0] for b in brands]

    competitors = []

    for brand in brands:
        # Find nearest store of this brand
        store = db.query(Store).filter(
            Store.brand == brand,
            Store.location.isnot(None)
        ).order_by(
            func.ST_Distance(Store.location, point)
        ).first()

        if store:
            # Calculate distance in miles
            distance_meters = db.query(
                func.ST_Distance(Store.location, point)
            ).filter(Store.id == store.id).scalar()

            distance_miles = round(distance_meters / 1609.34, 2) if distance_meters else 0

            competitors.append(NearestCompetitor(
                brand=brand,
                distance_miles=distance_miles,
                store=StoreResponse(
                    id=store.id,
                    brand=store.brand,
                    street=store.street,
                    city=store.city,
                    state=store.state,
                    postal_code=store.postal_code,
                    latitude=store.latitude,
                    longitude=store.longitude,
                )
            ))

    # Sort by distance
    competitors.sort(key=lambda x: x.distance_miles)

    return NearestCompetitorsResponse(
        latitude=request.latitude,
        longitude=request.longitude,
        competitors=competitors
    )


@router.get("/{store_id}", response_model=StoreResponse)
def get_location(store_id: int, db: Session = Depends(get_db)):
    """Get a single store by ID."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store
