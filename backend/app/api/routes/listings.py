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


# ============================================================================
# URL Import Endpoints (Added by Flash - Feb 3, 2026)
# ============================================================================

from app.services.url_import import import_from_url, ListingData


class URLImportRequest(BaseModel):
    """Request to import listing from URL."""
    url: str = Field(..., description="Listing URL (Crexi, LoopNet, or other CRE platform)")
    use_playwright: bool = Field(
        default=True,
        description="Use browser automation for more accurate extraction"
    )
    save_to_database: bool = Field(
        default=False,
        description="If True, automatically save to database. If False, return preview only."
    )


class URLImportResponse(BaseModel):
    """Response from URL import."""
    success: bool
    source: str
    external_id: Optional[str]
    listing_url: str
    
    # Extracted data
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    property_type: Optional[str]
    price: Optional[float]
    price_display: Optional[str]
    sqft: Optional[float]
    lot_size_acres: Optional[float]
    year_built: Optional[int]
    title: Optional[str]
    description: Optional[str]
    broker_name: Optional[str]
    broker_company: Optional[str]
    broker_phone: Optional[str]
    broker_email: Optional[str]
    images: List[str]
    
    # Metadata
    confidence: float
    extraction_method: str
    error_message: Optional[str]
    
    # Database info (if saved)
    listing_id: Optional[int] = None


@router.post("/import-url", response_model=URLImportResponse)
async def import_listing_from_url(
    request: URLImportRequest,
    db: Session = Depends(get_db)
):
    """
    Import a listing from a URL (Crexi, LoopNet, etc.).
    
    This endpoint intelligently extracts structured data from commercial real estate
    listing URLs. It works by:
    
    1. Detecting the platform (Crexi, LoopNet, etc.)
    2. Extracting data using platform-specific patterns
    3. Returning parsed data for review/editing
    4. Optionally saving to database if save_to_database=True
    
    **Use cases:**
    - Quick import: User pastes URL → data auto-fills → one click save
    - Browser bookmarklet: One-click add from any listing page
    - Batch import: Paste multiple URLs to import many listings
    
    **Confidence score:**
    - 80-100: High confidence, all key fields extracted
    - 60-79: Medium confidence, most fields extracted
    - 40-59: Low confidence, basic info extracted
    - 0-39: Failed extraction, manual entry recommended
    """
    try:
        # Extract data from URL
        logger.info(f"Importing listing from URL: {request.url}")
        listing_data: ListingData = await import_from_url(
            url=request.url,
            use_playwright=request.use_playwright
        )
        
        # Prepare response
        response = URLImportResponse(
            success=listing_data.success,
            source=listing_data.source,
            external_id=listing_data.external_id,
            listing_url=listing_data.listing_url,
            address=listing_data.address,
            city=listing_data.city,
            state=listing_data.state,
            postal_code=listing_data.postal_code,
            latitude=listing_data.latitude,
            longitude=listing_data.longitude,
            property_type=listing_data.property_type,
            price=listing_data.price,
            price_display=listing_data.price_display,
            sqft=listing_data.sqft,
            lot_size_acres=listing_data.lot_size_acres,
            year_built=listing_data.year_built,
            title=listing_data.title,
            description=listing_data.description,
            broker_name=listing_data.broker_name,
            broker_company=listing_data.broker_company,
            broker_phone=listing_data.broker_phone,
            broker_email=listing_data.broker_email,
            images=listing_data.images,
            confidence=listing_data.confidence,
            extraction_method=listing_data.extraction_method,
            error_message=listing_data.error_message
        )
        
        # Save to database if requested and extraction was successful
        if request.save_to_database and listing_data.success and listing_data.confidence >= 40:
            # Check if listing already exists
            existing = None
            if listing_data.external_id:
                existing = db.query(ScrapedListing).filter(
                    ScrapedListing.source == listing_data.source,
                    ScrapedListing.external_id == listing_data.external_id
                ).first()
            
            if existing:
                # Update existing listing
                existing.listing_url = listing_data.listing_url
                existing.address = listing_data.address or existing.address
                existing.city = listing_data.city or existing.city
                existing.state = listing_data.state or existing.state
                existing.postal_code = listing_data.postal_code or existing.postal_code
                existing.latitude = listing_data.latitude or existing.latitude
                existing.longitude = listing_data.longitude or existing.longitude
                existing.property_type = listing_data.property_type or existing.property_type
                existing.price = listing_data.price or existing.price
                existing.price_display = listing_data.price_display or existing.price_display
                existing.sqft = listing_data.sqft or existing.sqft
                existing.lot_size_acres = listing_data.lot_size_acres or existing.lot_size_acres
                existing.year_built = listing_data.year_built or existing.year_built
                existing.title = listing_data.title or existing.title
                existing.description = listing_data.description or existing.description
                existing.broker_name = listing_data.broker_name or existing.broker_name
                existing.broker_company = listing_data.broker_company or existing.broker_company
                existing.broker_phone = listing_data.broker_phone or existing.broker_phone
                existing.broker_email = listing_data.broker_email or existing.broker_email
                if listing_data.images:
                    existing.images = listing_data.images
                existing.last_verified = datetime.utcnow()
                existing.is_active = True
                
                response.listing_id = existing.id
                logger.info(f"Updated existing listing {existing.id}")
                
            else:
                # Create new listing
                new_listing = ScrapedListing(
                    source=listing_data.source,
                    external_id=listing_data.external_id,
                    listing_url=listing_data.listing_url,
                    address=listing_data.address,
                    city=listing_data.city or "Unknown",
                    state=listing_data.state or "XX",
                    postal_code=listing_data.postal_code,
                    latitude=listing_data.latitude,
                    longitude=listing_data.longitude,
                    property_type=listing_data.property_type,
                    price=listing_data.price,
                    price_display=listing_data.price_display,
                    sqft=listing_data.sqft,
                    lot_size_acres=listing_data.lot_size_acres,
                    year_built=listing_data.year_built,
                    title=listing_data.title,
                    description=listing_data.description,
                    broker_name=listing_data.broker_name,
                    broker_company=listing_data.broker_company,
                    broker_phone=listing_data.broker_phone,
                    broker_email=listing_data.broker_email,
                    images=listing_data.images,
                    raw_data={"url_import": True, "confidence": listing_data.confidence},
                    search_city=listing_data.city,
                    search_state=listing_data.state,
                    is_active=True,
                    last_verified=datetime.utcnow()
                )
                db.add(new_listing)
                db.flush()  # Get ID
                
                response.listing_id = new_listing.id
                logger.info(f"Created new listing {new_listing.id} from URL")
            
            db.commit()
        
        return response
        
    except Exception as e:
        logger.error(f"Error importing from URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import listing: {str(e)}"
        )


class BatchURLImportRequest(BaseModel):
    """Request to import multiple listings from URLs."""
    urls: List[str] = Field(..., description="List of listing URLs to import")
    use_playwright: bool = Field(default=True, description="Use browser automation")
    save_to_database: bool = Field(default=False, description="Auto-save successful imports")


class BatchURLImportResponse(BaseModel):
    """Response from batch URL import."""
    total_urls: int
    successful: int
    failed: int
    results: List[URLImportResponse]


@router.post("/import-urls-batch", response_model=BatchURLImportResponse)
async def import_listings_from_urls_batch(
    request: BatchURLImportRequest,
    db: Session = Depends(get_db)
):
    """
    Import multiple listings from URLs in batch.
    
    Useful for quickly importing many listings at once.
    Processes each URL sequentially to avoid overwhelming the target sites.
    """
    results = []
    successful = 0
    failed = 0
    
    for url in request.urls[:20]:  # Limit to 20 URLs per batch
        try:
            import_req = URLImportRequest(
                url=url,
                use_playwright=request.use_playwright,
                save_to_database=request.save_to_database
            )
            result = await import_listing_from_url(import_req, db)
            results.append(result)
            
            if result.success:
                successful += 1
            else:
                failed += 1
            
            # Small delay between requests to be polite
            await asyncio.sleep(1)
            
        except Exception as e:
            failed += 1
            logger.error(f"Batch import failed for {url}: {e}")
            # Add failed result
            results.append(URLImportResponse(
                success=False,
                source="unknown",
                external_id=None,
                listing_url=url,
                address=None,
                city=None,
                state=None,
                postal_code=None,
                latitude=None,
                longitude=None,
                property_type=None,
                price=None,
                price_display=None,
                sqft=None,
                lot_size_acres=None,
                year_built=None,
                title=None,
                description=None,
                broker_name=None,
                broker_company=None,
                broker_phone=None,
                broker_email=None,
                images=[],
                confidence=0.0,
                extraction_method="batch",
                error_message=str(e)
            ))
    
    return BatchURLImportResponse(
        total_urls=len(request.urls),
        successful=successful,
        failed=failed,
        results=results
    )
