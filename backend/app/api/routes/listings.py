"""
Listings API routes - Scrape and retrieve commercial property listings.

Endpoints for triggering scrapes and retrieving cached results from
Crexi, LoopNet, and other CRE platforms.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.scraped_listing import ScrapedListing
from app.services.listing_scraper import ListingScraperService, ScrapedProperty
from app.services.crexi_parser import parse_crexi_csv, filter_opportunities, import_to_database

router = APIRouter(prefix="/listings", tags=["listings"])
logger = logging.getLogger(__name__)

# Track ongoing scrape jobs
_active_scrapes: dict[str, dict] = {}


class ScrapeRequest(BaseModel):
    """Request to scrape listings for a location."""
    city: str = Field(..., description="City name")
    state: str = Field(..., min_length=2, max_length=2, description="2-letter state code")
    sources: list[str] = Field(
        default=["loopnet", "commercialcafe", "rofo"],
        description="Sources to scrape: loopnet, commercialcafe, rofo, crexi"
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
    transaction_type: Optional[str]
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
    """Background task to run the scrape via Firecrawl (or Playwright fallback)."""
    try:
        _active_scrapes[job_id]["status"] = "running"
        logger.info(f"Starting scrape job {job_id} for {city}, {state}")

        total_saved = 0
        source_counts = {}

        if FIRECRAWL_AVAILABLE:
            # Use Firecrawl (primary)
            service = FirecrawlScraperService()
            results = await service.search_area(
                city=city, state=state, sources=sources
            )

            # Filter through existing criteria and save
            for result in results:
                listing_data = firecrawl_result_to_scraped_listing(result, city, state)

                # Geocode if missing coordinates
                listing_data = await backfill_coordinates(listing_data)

                # Skip listings without coordinates
                if not listing_data.get("latitude") or not listing_data.get("longitude"):
                    continue

                source_name = listing_data.get("source", "unknown")
                source_counts[source_name] = source_counts.get(source_name, 0) + 1

                # Upsert to database
                external_id = listing_data.get("external_id")
                existing = None
                if external_id:
                    existing = db.query(ScrapedListing).filter(
                        ScrapedListing.source == source_name,
                        ScrapedListing.external_id == external_id
                    ).first()

                if existing:
                    for key, value in listing_data.items():
                        if value is not None:
                            setattr(existing, key, value)
                    existing.last_verified = datetime.utcnow()
                else:
                    new_listing = ScrapedListing(**listing_data)
                    db.add(new_listing)
                    total_saved += 1

            db.commit()
        else:
            # Fallback to Playwright (legacy)
            service = ListingScraperService()
            results = await service.search_all(
                city=city, state=state, property_types=property_types,
                sources=sources, headless=True
            )
            for source, properties in results.items():
                source_counts[source] = len(properties)
                for prop in properties:
                    existing = db.query(ScrapedListing).filter(
                        ScrapedListing.source == prop.source,
                        ScrapedListing.external_id == prop.external_id
                    ).first() if prop.external_id else None
                    if existing:
                        for key, value in _property_to_db(prop, city, state).items():
                            if value is not None:
                                setattr(existing, key, value)
                        existing.last_verified = datetime.utcnow()
                    else:
                        new_listing = ScrapedListing(**_property_to_db(prop, city, state))
                        db.add(new_listing)
                        total_saved += 1
                db.commit()

        _active_scrapes[job_id]["status"] = "completed"
        _active_scrapes[job_id]["results"] = source_counts
        _active_scrapes[job_id]["total_saved"] = total_saved
        _active_scrapes[job_id]["method"] = "firecrawl" if FIRECRAWL_AVAILABLE else "playwright"
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
    # Check if any scraping method is available
    if not FIRECRAWL_AVAILABLE:
        # Fall back to credential check for Playwright
        has_crexi = bool(settings.crexi_username and settings.CREXI_PASSWORD)
        has_loopnet = bool(settings.LOOPNET_USERNAME and settings.LOOPNET_PASSWORD)

        if 'crexi' in request.sources and not has_crexi:
            raise HTTPException(
                status_code=400,
                detail="Neither Firecrawl nor Crexi credentials configured. Set FIRECRAWL_API_KEY or CREXI_USERNAME/CREXI_PASSWORD."
            )

        if 'loopnet' in request.sources and not has_loopnet:
            raise HTTPException(
                status_code=400,
                detail="Neither Firecrawl nor LoopNet credentials configured. Set FIRECRAWL_API_KEY or LOOPNET_USERNAME/LOOPNET_PASSWORD."
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
            transaction_type=getattr(l, 'transaction_type', None),
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
            transaction_type=getattr(l, 'transaction_type', None),
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
            "configured": bool(settings.crexi_username and settings.CREXI_PASSWORD),
            "username_set": bool(settings.crexi_username),
        },
        "loopnet": {
            "configured": bool(settings.LOOPNET_USERNAME and settings.LOOPNET_PASSWORD),
            "username_set": bool(settings.LOOPNET_USERNAME),
        }
    }


@router.get("/diagnostics")
async def get_diagnostics():
    """
    Check scraping service status and dependencies.

    Returns status for Firecrawl (primary) and Playwright (legacy fallback).
    """
    diagnostics = {
        "firecrawl": {
            "available": FIRECRAWL_AVAILABLE,
            "error": FIRECRAWL_ERROR,
            "credits": credit_tracker.status() if FIRECRAWL_AVAILABLE else None,
        },
        "playwright": {
            "available": PLAYWRIGHT_AVAILABLE,
            "error": PLAYWRIGHT_ERROR,
            "note": "Legacy fallback — being replaced by Firecrawl",
        },
        "crexi": {
            "automation_loaded": CREXI_AVAILABLE,
            "error": CREXI_ERROR_MESSAGE,
            "credentials": {
                "username_set": bool(settings.crexi_username),
                "password_set": bool(settings.CREXI_PASSWORD),
            }
        },
        "csv_upload": {
            "available": True,
            "note": "Always available as fallback",
        },
        "recommendations": []
    }

    # Generate recommendations
    if not FIRECRAWL_AVAILABLE:
        diagnostics["recommendations"].append(
            "Set FIRECRAWL_API_KEY environment variable for automated scraping"
        )

    if FIRECRAWL_AVAILABLE and credit_tracker.remaining < 50:
        diagnostics["recommendations"].append(
            f"Low Firecrawl credits: {credit_tracker.remaining} remaining this month"
        )

    if not diagnostics["recommendations"]:
        diagnostics["recommendations"].append("All systems operational!")

    return diagnostics


@router.get("/firecrawl-status")
async def get_firecrawl_status():
    """Get Firecrawl API credit usage and availability."""
    if not FIRECRAWL_AVAILABLE:
        return {
            "available": False,
            "error": FIRECRAWL_ERROR,
        }
    return {
        "available": True,
        **credit_tracker.status(),
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

# ---------------------------------------------------------------------------
# Lazy-load scrapers to prevent startup failures if dependencies unavailable
# ---------------------------------------------------------------------------

# Firecrawl (primary scraping method)
FIRECRAWL_AVAILABLE = False
FIRECRAWL_ERROR = None
try:
    from app.services.firecrawl_scraper import (
        FirecrawlScraperService,
        FirecrawlBudgetExceeded,
        firecrawl_result_to_scraped_listing,
        backfill_coordinates,
        credit_tracker,
        is_firecrawl_available,
    )
    if settings.FIRECRAWL_API_KEY and settings.FIRECRAWL_API_KEY.strip():
        FIRECRAWL_AVAILABLE = True
        logger.info("Firecrawl service available")
    else:
        FIRECRAWL_ERROR = "FIRECRAWL_API_KEY not configured"
        logger.warning(FIRECRAWL_ERROR)
except ImportError as e:
    FIRECRAWL_ERROR = f"firecrawl-py not installed: {e}"
    logger.warning(FIRECRAWL_ERROR)
except Exception as e:
    FIRECRAWL_ERROR = f"Firecrawl import error: {type(e).__name__}: {e}"
    logger.warning(FIRECRAWL_ERROR)

# Playwright / Crexi automation (legacy fallback)
CREXI_AVAILABLE = False
CREXI_ERROR_MESSAGE = None
PLAYWRIGHT_AVAILABLE = False
PLAYWRIGHT_ERROR = None

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError as e:
    PLAYWRIGHT_ERROR = f"Playwright not installed: {e}"
except Exception as e:
    PLAYWRIGHT_ERROR = f"Playwright import error: {type(e).__name__}: {e}"

try:
    from app.services.crexi_automation import fetch_crexi_area as _playwright_fetch_crexi_area, CrexiAutomationError
    CREXI_AVAILABLE = True
except ImportError as e:
    CREXI_ERROR_MESSAGE = f"Crexi module import failed: {e}"
except Exception as e:
    CREXI_ERROR_MESSAGE = f"Crexi automation error: {type(e).__name__}: {e}"

# Stub classes for type safety when not available
if not CREXI_AVAILABLE:
    class CrexiAutomationError(Exception):
        pass

    async def _playwright_fetch_crexi_area(*args, **kwargs):
        error_msg = CREXI_ERROR_MESSAGE or "Crexi automation not available"
        raise CrexiAutomationError(error_msg)


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
        logger.info(f"Importing listing from URL: {request.url}")

        # Try Firecrawl first (primary), then fall back to HTTP extraction
        listing_data = None
        if FIRECRAWL_AVAILABLE:
            try:
                service = FirecrawlScraperService()
                fc_result = await service.scrape_single_url(request.url)

                if fc_result.get("success"):
                    # Geocode if missing coordinates
                    data = fc_result.get("data", {})
                    if not (data.get("latitude") and data.get("longitude")):
                        data = await backfill_coordinates(data)
                        fc_result["data"] = data

                    listing_data = ListingData(
                        success=True,
                        source=fc_result.get("source", "unknown"),
                        external_id=fc_result.get("external_id"),
                        listing_url=fc_result.get("listing_url", request.url),
                        address=data.get("address"),
                        city=data.get("city"),
                        state=data.get("state"),
                        postal_code=data.get("postal_code"),
                        latitude=data.get("latitude"),
                        longitude=data.get("longitude"),
                        property_type=data.get("property_type"),
                        price=data.get("price"),
                        price_display=data.get("price_display"),
                        sqft=data.get("sqft"),
                        lot_size_acres=data.get("lot_size_acres"),
                        year_built=data.get("year_built"),
                        title=data.get("title"),
                        description=data.get("description"),
                        broker_name=data.get("broker_name"),
                        broker_company=data.get("broker_company"),
                        broker_phone=data.get("broker_phone"),
                        broker_email=data.get("broker_email"),
                        images=data.get("images", []),
                        confidence=fc_result.get("confidence", 0.0),
                        extraction_method="firecrawl",
                    )
                    logger.info(f"Firecrawl extraction successful (confidence: {listing_data.confidence})")
            except FirecrawlBudgetExceeded:
                logger.warning("Firecrawl budget exceeded — falling back to HTTP extraction")
            except Exception as e:
                logger.warning(f"Firecrawl extraction failed — falling back to HTTP: {e}")

        # Fallback to existing HTTP/Playwright extraction
        if listing_data is None:
            listing_data = await import_from_url(
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


# ============================================================================
# Crexi CSV Export Automation (Added by Subagent - Feb 4, 2026)
# ============================================================================


class CrexiAreaRequest(BaseModel):
    """Request to fetch Crexi listings for an area via automated export."""
    location: str = Field(..., description="Location to search (e.g., 'Des Moines, IA')")
    property_types: Optional[List[str]] = Field(
        default=None,
        description="Property types to include (default: ['Land', 'Retail', 'Office'])"
    )
    force_refresh: bool = Field(
        default=False,
        description="Force new export even if cached data exists"
    )


class CrexiAreaResponse(BaseModel):
    """Response from Crexi area fetch."""
    success: bool
    imported: int
    updated: int
    total_filtered: int
    empty_land_count: int
    small_building_count: int
    cached: bool
    cache_age_minutes: Optional[int]
    timestamp: str
    expires_at: str
    location: str
    message: Optional[str]


@router.post("/fetch-crexi-area", response_model=CrexiAreaResponse)
async def fetch_crexi_area_endpoint(
    request: CrexiAreaRequest,
    db: Session = Depends(get_db)
):
    """
    Fetch Crexi listings for a location via automated CSV export.
    
    This endpoint:
    1. Checks cache (24hr TTL per location)
    2. If cached and not force_refresh, returns cached data
    3. Otherwise, triggers Playwright automation to:
       - Log into Crexi
       - Search the location
       - Apply filters (For Sale + property types)
       - Download CSV export
       - Parse and filter opportunities
       - Import to database
    
    **Filtering criteria:**
    - Empty land: 0.8-2 acres, Type contains "Land"
    - Small buildings: 2500-6000 sqft, ≤1 unit, Retail/Office/Industrial
    
    **Security:** Logs every session, only searches explicitly tasked markets.
    
    **Performance:** ~30-90 seconds for fresh export, <1 second for cached.
    """
    # Check if any scraping method is available
    if not FIRECRAWL_AVAILABLE and not CREXI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="No scraping method available. Configure FIRECRAWL_API_KEY or Playwright + Crexi credentials."
        )

    try:
        # Check for cached data
        cache_cutoff = datetime.utcnow() - timedelta(hours=24)

        # Parse location
        if "," in request.location:
            search_city = request.location.split(",")[0].strip()
            search_state = request.location.split(",")[1].strip()
        else:
            search_city = request.location
            search_state = None

        if not request.force_refresh:
            # Check for recent cache (any source — Firecrawl results also have source="crexi")
            cache_query = db.query(ScrapedListing).filter(
                ScrapedListing.search_city == search_city,
                ScrapedListing.scraped_at > cache_cutoff,
                ScrapedListing.is_active == True,
            )

            if search_state:
                cache_query = cache_query.filter(ScrapedListing.search_state == search_state.upper())

            cached_listings = cache_query.all()

            if cached_listings:
                oldest = min(l.scraped_at for l in cached_listings)
                cache_age = int((datetime.utcnow() - oldest).total_seconds() / 60)

                empty_land = sum(1 for l in cached_listings
                               if l.raw_data and l.raw_data.get('match_category') == 'empty_land')
                small_building = sum(1 for l in cached_listings
                                   if l.raw_data and l.raw_data.get('match_category') == 'small_building')

                expires_at = oldest + timedelta(hours=24)

                return CrexiAreaResponse(
                    success=True,
                    imported=0,
                    updated=0,
                    total_filtered=len(cached_listings),
                    empty_land_count=empty_land,
                    small_building_count=small_building,
                    cached=True,
                    cache_age_minutes=cache_age,
                    timestamp=oldest.isoformat(),
                    expires_at=expires_at.isoformat(),
                    location=request.location,
                    message=f"Using {len(cached_listings)} cached listings from {cache_age} minutes ago"
                )

        # No cache or force refresh — scrape fresh data
        if FIRECRAWL_AVAILABLE:
            # Primary: Firecrawl area search
            logger.info(f"Starting Firecrawl area search for: {request.location}")

            service = FirecrawlScraperService()
            results = await service.search_area(
                city=search_city,
                state=search_state or "",
                sources=["loopnet", "commercialcafe", "rofo"],
            )

            # Import ALL listings directly to scraped_listings table.
            # Unlike CSV upload (which filters to land/small buildings only),
            # automated scraping imports everything for the Active Listings layer.
            # The Opportunities layer scoring handles ranking separately.
            imported_count = 0
            updated_count = 0
            empty_land_count = 0
            small_building_count = 0

            for result in results:
                # Backfill coordinates via Mapbox geocoding
                data = result.get("data", {})
                if not (data.get("latitude") and data.get("longitude")):
                    data = await backfill_coordinates(data)
                    result["data"] = data

                # Convert to scraped_listing dict
                listing_dict = firecrawl_result_to_scraped_listing(
                    result,
                    search_city=search_city,
                    search_state=search_state,
                )

                # Skip listings without coordinates (can't show on map)
                if not (listing_dict.get("latitude") and listing_dict.get("longitude")):
                    continue

                # Track criteria-matching listings for stats
                prop_type = (data.get("property_type") or "").lower()
                lot_acres = data.get("lot_size_acres")
                sqft = data.get("sqft")
                if lot_acres and 0.8 <= lot_acres <= 2.0 and "land" in prop_type:
                    empty_land_count += 1
                elif sqft and 2500 <= sqft <= 6000 and any(t in prop_type for t in ["retail", "office", "industrial"]):
                    small_building_count += 1

                # Upsert to database
                try:
                    source = listing_dict.get("source", "unknown")
                    ext_id = listing_dict.get("external_id")

                    existing = None
                    if ext_id:
                        existing = db.query(ScrapedListing).filter(
                            ScrapedListing.source == source,
                            ScrapedListing.external_id == ext_id,
                        ).first()

                    if existing:
                        for key, val in listing_dict.items():
                            if val is not None and hasattr(existing, key):
                                setattr(existing, key, val)
                        updated_count += 1
                    else:
                        new_listing = ScrapedListing(**{
                            k: v for k, v in listing_dict.items()
                            if hasattr(ScrapedListing, k)
                        })
                        db.add(new_listing)
                        imported_count += 1
                except Exception as e:
                    logger.warning(f"Failed to import listing: {e}")

            db.commit()
            now = datetime.utcnow()
            expires_at = now + timedelta(hours=24)
            total_saved = imported_count + updated_count

            return CrexiAreaResponse(
                success=True,
                imported=imported_count,
                updated=updated_count,
                total_filtered=total_saved,
                empty_land_count=empty_land_count,
                small_building_count=small_building_count,
                cached=False,
                cache_age_minutes=0,
                timestamp=now.isoformat(),
                expires_at=expires_at.isoformat(),
                location=request.location,
                message=(
                    f"Firecrawl scraped {len(results)} listings from LoopNet+CommercialCafe+Rofo (sale+lease). "
                    f"Saved {total_saved} to database ({imported_count} new, {updated_count} updated). "
                    f"{empty_land_count} land + {small_building_count} buildings match site criteria. "
                    f"Credits used: ~{credit_tracker.credits_used}"
                ),
            )

        else:
            # Fallback: Playwright automation
            logger.info(f"Starting Playwright automation for: {request.location}")
            csv_path, import_result = await _playwright_fetch_crexi_area(
                location=request.location,
                property_types=request.property_types,
                db=db
            )

            expires_at = import_result.timestamp + timedelta(hours=24)
            return CrexiAreaResponse(
                success=True,
                imported=import_result.total_imported,
                updated=import_result.total_updated,
                total_filtered=import_result.total_filtered,
                empty_land_count=import_result.empty_land_count,
                small_building_count=import_result.small_building_count,
                cached=False,
                cache_age_minutes=0,
                timestamp=import_result.timestamp.isoformat(),
                expires_at=expires_at.isoformat(),
                location=request.location,
                message=f"Imported {import_result.total_imported} new listings via Playwright"
            )

    except (CrexiAutomationError, FirecrawlBudgetExceeded) as e:
        logger.error(f"Area fetch failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Area fetch failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in fetch_crexi_area: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch data: {str(e)}"
        )


# ============================================================================
# Crexi CSV Upload (Replaces fragile Playwright automation)
# ============================================================================


@router.post("/upload-crexi-csv", response_model=CrexiAreaResponse)
async def upload_crexi_csv(
    file: UploadFile = File(...),
    location: str = Form(""),
    db: Session = Depends(get_db)
):
    """
    Upload a Crexi CSV/Excel export and import matching listings.

    Workflow:
    1. User exports CSV from Crexi.com manually
    2. User uploads the file here
    3. Backend parses, filters (0.8-2ac land, 2500-6000 sqft buildings), and imports

    Accepts .xlsx, .xls, and .csv files in Crexi's 24-column export format.
    """
    import tempfile
    import os

    # Validate file type
    filename = file.filename or ""
    valid_extensions = (".xlsx", ".xls", ".csv")
    if not any(filename.lower().endswith(ext) for ext in valid_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Accepted formats: {', '.join(valid_extensions)}"
        )

    # Save upload to temp file
    suffix = os.path.splitext(filename)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # Parse using existing Crexi parser
        listings = parse_crexi_csv(tmp.name)

        if not listings:
            return CrexiAreaResponse(
                success=True,
                imported=0,
                updated=0,
                total_filtered=0,
                empty_land_count=0,
                small_building_count=0,
                cached=False,
                cache_age_minutes=0,
                timestamp=datetime.utcnow().isoformat(),
                expires_at=(datetime.utcnow() + timedelta(hours=24)).isoformat(),
                location=location or "Unknown",
                message="CSV parsed but contained no listings. Check that the file is a Crexi export.",
            )

        # Filter to opportunities
        filtered, stats = filter_opportunities(listings)

        # Derive location from CSV data if not provided
        if not location.strip() and filtered:
            first = filtered[0]
            location = f"{first.city}, {first.state}" if first.city and first.state else first.city or "Unknown"
        elif not location.strip():
            first = listings[0]
            location = f"{first.city}, {first.state}" if first.city and first.state else first.city or "Unknown"

        # Import to database
        result = import_to_database(filtered, location, db)

        return CrexiAreaResponse(
            success=True,
            imported=result.total_imported,
            updated=result.total_updated,
            total_filtered=result.total_filtered,
            empty_land_count=result.empty_land_count,
            small_building_count=result.small_building_count,
            cached=False,
            cache_age_minutes=0,
            timestamp=result.timestamp.isoformat(),
            expires_at=(result.timestamp + timedelta(hours=24)).isoformat(),
            location=location,
            message=(
                f"Parsed {len(listings)} listings, {result.total_filtered} match criteria. "
                f"Imported {result.total_imported} new, updated {result.total_updated}."
            ),
        )

    except ValueError as e:
        logger.error(f"CSV parse error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"CSV upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")
    finally:
        os.unlink(tmp.name)


# ============================================================================
# Automated Market Refresh (Firecrawl bulk scraping)
# ============================================================================

# Target market cities for automated scraping
TARGET_MARKET_CITIES = [
    ("Des Moines", "IA"), ("Cedar Rapids", "IA"), ("Davenport", "IA"), ("Iowa City", "IA"),
    ("Omaha", "NE"), ("Lincoln", "NE"), ("Grand Island", "NE"),
    ("Las Vegas", "NV"), ("Reno", "NV"), ("Henderson", "NV"),
    ("Boise", "ID"), ("Meridian", "ID"), ("Nampa", "ID"),
]


class RefreshAllMarketsResponse(BaseModel):
    """Response from refresh-all-markets endpoint."""
    success: bool
    total_cities: int
    cities_scraped: int
    cities_cached: int
    cities_failed: int
    total_listings_imported: int
    total_listings_updated: int
    credits_used_estimate: int
    results: List[Dict]


@router.post("/refresh-all-markets", response_model=RefreshAllMarketsResponse)
async def refresh_all_markets(
    force_refresh: bool = False,
    db: Session = Depends(get_db),
):
    """
    Scrape LoopNet, CommercialCafe, and Rofo for ALL target market cities.

    Iterates through all target cities (IA, NE, NV, ID) and scrapes
    search results from all platforms (sale + lease). Each city checks
    the 24hr cache first — only scrapes if data is stale.

    Estimated credits: ~130 total (13 cities x 3 platforms x 2 types x ~2 pages).
    """
    if not FIRECRAWL_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Firecrawl not configured. Set FIRECRAWL_API_KEY to enable automated scraping."
        )

    results = []
    cities_scraped = 0
    cities_cached = 0
    cities_failed = 0
    total_imported = 0
    total_updated = 0
    credits_before = credit_tracker.credits_used

    for city, state in TARGET_MARKET_CITIES:
        location = f"{city}, {state}"
        try:
            # Use the existing fetch endpoint logic
            area_request = CrexiAreaRequest(
                location=location,
                force_refresh=force_refresh,
            )
            response = await fetch_crexi_area_endpoint(area_request, db)

            if response.cached:
                cities_cached += 1
            else:
                cities_scraped += 1
                total_imported += response.imported
                total_updated += response.updated

            results.append({
                "location": location,
                "status": "cached" if response.cached else "scraped",
                "imported": response.imported,
                "updated": response.updated,
                "total_filtered": response.total_filtered,
            })

        except Exception as e:
            cities_failed += 1
            logger.error(f"Failed to refresh {location}: {e}")
            results.append({
                "location": location,
                "status": "failed",
                "error": str(e),
            })

    credits_used = credit_tracker.credits_used - credits_before

    return RefreshAllMarketsResponse(
        success=cities_failed < len(TARGET_MARKET_CITIES),
        total_cities=len(TARGET_MARKET_CITIES),
        cities_scraped=cities_scraped,
        cities_cached=cities_cached,
        cities_failed=cities_failed,
        total_listings_imported=total_imported,
        total_listings_updated=total_updated,
        credits_used_estimate=credits_used,
        results=results,
    )
