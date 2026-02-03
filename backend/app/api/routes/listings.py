"""
Listings API routes - Scrape and retrieve commercial property listings.

Endpoints for triggering scrapes and retrieving cached results from
Crexi, LoopNet, and other CRE platforms.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.scraped_listing import ScrapedListing
from app.services.listing_scraper import ListingScraperService, ScrapedProperty

router = APIRouter(prefix="/listings", tags=["listings"])
logger = logging.getLogger(__name__)

# Track ongoing scrape jobs
_active_scrapes: dict[str, dict] = {}


class ScrapeRequest(BaseModel):
    """Request to scrape listings for a location."""
    city: str = Field(..., description="City name")
    state: str = Field(..., min_length=2, max_length=2, description="2-letter state code")
    sources: list[str] = Field(
        default=["crexi", "loopnet"],
        description="Sources to scrape: crexi, loopnet"
    )
    property_types: Optional[list[str]] = Field(
        default=None,
        description="Property types: Retail, Land, Office, Industrial"
    )
    force_refresh: bool = Field(
        default=False,
        description="Force fresh scrape even if cached results exist"
    )


class ScrapeResponse(BaseModel):
    """Response from scrape request."""
    job_id: str
    status: str  # "started", "running", "completed", "failed"
    message: str


class ListingResponse(BaseModel):
    """Single listing response."""
    id: int
    source: str
    external_id: Optional[str]
    listing_url: Optional[str]
    address: Optional[str]
    city: str
    state: str
    postal_code: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    property_type: Optional[str]
    price: Optional[float]
    price_display: Optional[str]
    sqft: Optional[float]
    lot_size_acres: Optional[float]
    title: Optional[str]
    broker_name: Optional[str]
    broker_company: Optional[str]
    images: Optional[list[str]]
    scraped_at: datetime

    class Config:
        from_attributes = True


class ListingsSearchResponse(BaseModel):
    """Response for listing search."""
    total: int
    listings: list[ListingResponse]
    sources: list[str]
    cached: bool
    cache_age_minutes: Optional[int]


def _property_to_db(prop: ScrapedProperty, search_city: str, search_state: str) -> dict:
    """Convert ScrapedProperty to database dict."""
    return {
        "source": prop.source,
        "external_id": prop.external_id,
        "listing_url": prop.listing_url,
        "address": prop.address,
        "city": prop.city or search_city,
        "state": prop.state or search_state,
        "postal_code": prop.postal_code,
        "latitude": prop.latitude,
        "longitude": prop.longitude,
        "property_type": prop.property_type,
        "price": prop.price,
        "price_display": prop.price_display,
        "sqft": prop.sqft,
        "lot_size_acres": prop.lot_size_acres,
        "year_built": prop.year_built,
        "title": prop.title,
        "description": prop.description,
        "broker_name": prop.broker_name,
        "broker_company": prop.broker_company,
        "broker_phone": prop.broker_phone,
        "broker_email": prop.broker_email,
        "images": prop.images,
        "raw_data": prop.raw_data,
        "search_city": search_city,
        "search_state": search_state,
    }


async def _run_scrape(
    job_id: str,
    city: str,
    state: str,
    sources: list[str],
    property_types: list[str],
    db: Session
):
    """Background task to run the scrape."""
    try:
        _active_scrapes[job_id]["status"] = "running"
        logger.info(f"Starting scrape job {job_id} for {city}, {state}")

        service = ListingScraperService()
        results = await service.search_all(
            city=city,
            state=state,
            property_types=property_types,
            sources=sources,
            headless=True
        )

        # Save results to database
        total_saved = 0
        for source, properties in results.items():
            for prop in properties:
                # Check if listing already exists
                existing = db.query(ScrapedListing).filter(
                    ScrapedListing.source == prop.source,
                    ScrapedListing.external_id == prop.external_id
                ).first() if prop.external_id else None

                if existing:
                    # Update existing listing
                    for key, value in _property_to_db(prop, city, state).items():
                        if value is not None:
                            setattr(existing, key, value)
                    existing.last_verified = datetime.utcnow()
                else:
                    # Create new listing
                    new_listing = ScrapedListing(**_property_to_db(prop, city, state))
                    db.add(new_listing)
                    total_saved += 1

            db.commit()

        _active_scrapes[job_id]["status"] = "completed"
        _active_scrapes[job_id]["results"] = {
            source: len(props) for source, props in results.items()
        }
        _active_scrapes[job_id]["total_saved"] = total_saved
        logger.info(f"Scrape job {job_id} completed: {total_saved} new listings saved")

    except Exception as e:
        logger.error(f"Scrape job {job_id} failed: {e}")
        _active_scrapes[job_id]["status"] = "failed"
        _active_scrapes[job_id]["error"] = str(e)


@router.post("/scrape", response_model=ScrapeResponse)
async def trigger_scrape(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger a scrape of commercial listings.

    This starts a background job that will scrape Crexi and/or LoopNet
    for commercial property listings in the specified location.

    Results are cached in the database and can be retrieved via
    GET /listings/search endpoint.
    """
    # Check if credentials are configured
    has_crexi = bool(settings.CREXI_USERNAME and settings.CREXI_PASSWORD)
    has_loopnet = bool(settings.LOOPNET_USERNAME and settings.LOOPNET_PASSWORD)

    if 'crexi' in request.sources and not has_crexi:
        raise HTTPException(
            status_code=400,
            detail="Crexi credentials not configured. Set CREXI_USERNAME and CREXI_PASSWORD."
        )

    if 'loopnet' in request.sources and not has_loopnet:
        raise HTTPException(
            status_code=400,
            detail="LoopNet credentials not configured. Set LOOPNET_USERNAME and LOOPNET_PASSWORD."
        )

    # Check for recent cache unless force_refresh
    if not request.force_refresh:
        cache_cutoff = datetime.utcnow() - timedelta(hours=24)
        cached_count = db.query(ScrapedListing).filter(
            ScrapedListing.search_city == request.city,
            ScrapedListing.search_state == request.state.upper(),
            ScrapedListing.scraped_at > cache_cutoff
        ).count()

        if cached_count > 0:
            return ScrapeResponse(
                job_id="cached",
                status="completed",
                message=f"Using {cached_count} cached listings from last 24 hours. Use force_refresh=true to scrape fresh data."
            )

    # Create job ID
    job_id = f"{request.city.lower().replace(' ', '-')}-{request.state.upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Check if scrape is already running
    for existing_id, job in _active_scrapes.items():
        if job["city"] == request.city and job["state"] == request.state and job["status"] == "running":
            return ScrapeResponse(
                job_id=existing_id,
                status="running",
                message="A scrape for this location is already in progress."
            )

    # Register job
    _active_scrapes[job_id] = {
        "city": request.city,
        "state": request.state.upper(),
        "sources": request.sources,
        "status": "started",
        "started_at": datetime.utcnow().isoformat()
    }

    # Start background scrape
    background_tasks.add_task(
        _run_scrape,
        job_id,
        request.city,
        request.state.upper(),
        request.sources,
        request.property_types,
        db
    )

    return ScrapeResponse(
        job_id=job_id,
        status="started",
        message=f"Scrape started for {request.city}, {request.state}. Check status at GET /listings/scrape/{job_id}"
    )


@router.get("/scrape/{job_id}")
async def get_scrape_status(job_id: str):
    """Get the status of a scrape job."""
    if job_id not in _active_scrapes:
        raise HTTPException(status_code=404, detail="Job not found")

    return _active_scrapes[job_id]


@router.get("/search", response_model=ListingsSearchResponse)
async def search_listings(
    city: str,
    state: str,
    source: Optional[str] = None,
    property_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Search cached listings for a location.

    Returns listings that have been previously scraped for the given city/state.
    Use POST /listings/scrape to trigger a fresh scrape.
    """
    query = db.query(ScrapedListing).filter(
        ScrapedListing.search_city == city,
        ScrapedListing.search_state == state.upper(),
        ScrapedListing.is_active == True
    )

    if source:
        query = query.filter(ScrapedListing.source == source)

    if property_type:
        query = query.filter(ScrapedListing.property_type == property_type)

    if min_price:
        query = query.filter(ScrapedListing.price >= min_price)

    if max_price:
        query = query.filter(ScrapedListing.price <= max_price)

    # Get total before limit
    total = query.count()

    # Apply limit and order by newest
    listings = query.order_by(ScrapedListing.scraped_at.desc()).limit(limit).all()

    # Determine cache age
    cache_age = None
    cached = False
    if listings:
        oldest = min(l.scraped_at for l in listings)
        cache_age = int((datetime.utcnow() - oldest).total_seconds() / 60)
        cached = True

    # Get unique sources
    sources = list(set(l.source for l in listings))

    return ListingsSearchResponse(
        total=total,
        listings=[ListingResponse(
            id=l.id,
            source=l.source,
            external_id=l.external_id,
            listing_url=l.listing_url,
            address=l.address,
            city=l.city,
            state=l.state,
            postal_code=l.postal_code,
            latitude=l.latitude,
            longitude=l.longitude,
            property_type=l.property_type,
            price=l.price,
            price_display=l.price_display,
            sqft=l.sqft,
            lot_size_acres=l.lot_size_acres,
            title=l.title,
            broker_name=l.broker_name,
            broker_company=l.broker_company,
            images=l.images,
            scraped_at=l.scraped_at
        ) for l in listings],
        sources=sources,
        cached=cached,
        cache_age_minutes=cache_age
    )


class BoundsSearchRequest(BaseModel):
    """Request for bounds-based listing search."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float
    source: Optional[str] = None
    property_type: Optional[str] = None
    limit: int = Field(default=100, le=500)


@router.post("/search-bounds", response_model=ListingsSearchResponse)
async def search_listings_by_bounds(
    request: BoundsSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Search cached listings within geographic bounds.

    Returns listings that have lat/lng coordinates within the specified bounding box.
    This is useful for showing listings within the current map viewport.
    """
    query = db.query(ScrapedListing).filter(
        ScrapedListing.latitude.isnot(None),
        ScrapedListing.longitude.isnot(None),
        ScrapedListing.latitude >= request.min_lat,
        ScrapedListing.latitude <= request.max_lat,
        ScrapedListing.longitude >= request.min_lng,
        ScrapedListing.longitude <= request.max_lng,
        ScrapedListing.is_active == True
    )

    if request.source:
        query = query.filter(ScrapedListing.source == request.source)

    if request.property_type:
        query = query.filter(ScrapedListing.property_type == request.property_type)

    # Get total before limit
    total = query.count()

    # Apply limit and order by newest
    listings = query.order_by(ScrapedListing.scraped_at.desc()).limit(request.limit).all()

    # Determine cache age
    cache_age = None
    cached = False
    if listings:
        oldest = min(l.scraped_at for l in listings)
        cache_age = int((datetime.utcnow() - oldest).total_seconds() / 60)
        cached = True

    # Get unique sources
    sources = list(set(l.source for l in listings))

    return ListingsSearchResponse(
        total=total,
        listings=[ListingResponse(
            id=l.id,
            source=l.source,
            external_id=l.external_id,
            listing_url=l.listing_url,
            address=l.address,
            city=l.city,
            state=l.state,
            postal_code=l.postal_code,
            latitude=l.latitude,
            longitude=l.longitude,
            property_type=l.property_type,
            price=l.price,
            price_display=l.price_display,
            sqft=l.sqft,
            lot_size_acres=l.lot_size_acres,
            title=l.title,
            broker_name=l.broker_name,
            broker_company=l.broker_company,
            images=l.images,
            scraped_at=l.scraped_at
        ) for l in listings],
        sources=sources,
        cached=cached,
        cache_age_minutes=cache_age
    )


@router.get("/sources")
async def get_configured_sources():
    """Check which scraping sources are configured."""
    return {
        "crexi": {
            "configured": bool(settings.CREXI_USERNAME and settings.CREXI_PASSWORD),
            "username_set": bool(settings.CREXI_USERNAME),
        },
        "loopnet": {
            "configured": bool(settings.LOOPNET_USERNAME and settings.LOOPNET_PASSWORD),
            "username_set": bool(settings.LOOPNET_USERNAME),
        }
    }


@router.delete("/{listing_id}")
async def deactivate_listing(
    listing_id: int,
    db: Session = Depends(get_db)
):
    """Mark a listing as inactive (e.g., sold or removed)."""
    listing = db.query(ScrapedListing).filter(ScrapedListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.is_active = False
    db.commit()

    return {"message": f"Listing {listing_id} marked as inactive"}
