"""
Core Analysis API endpoints.

Includes:
- Trade area analysis (POI discovery via Mapbox/Google Places)
- Demographics (ArcGIS GeoEnrichment)
- StreetLight traffic counts
- API key checks (consolidated + legacy individual)
- Store re-geocoding
- Store coordinate validation
- Mapbox Places trade area (POC)
"""
import asyncio
import httpx
import logging
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text

from app.services.places import fetch_nearby_pois, TradeAreaAnalysis
from app.services.arcgis import fetch_demographics, DemographicsResponse
from app.services.streetlight import (
    fetch_traffic_counts,
    TrafficAnalysis,
    StreetlightClient,
    SegmentCountEstimate,
)
from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])

# Track re-geocoding progress
regeocode_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "updated": 0,
    "failed": 0,
    "message": "Not started"
}


# =============================================================================
# Trade Area Analysis
# =============================================================================

class TradeAreaRequest(BaseModel):
    """Request model for trade area analysis."""
    latitude: float
    longitude: float
    radius_miles: float = 1.0  # Default 1 mile radius


@router.post("/trade-area/", response_model=TradeAreaAnalysis)
async def analyze_trade_area(request: TradeAreaRequest):
    """
    Analyze the trade area around a location.

    Fetches nearby points of interest (POIs) within the specified radius.
    Categories: anchors, quick_service, restaurants, retail, entertainment, services.

    Uses Mapbox Search Box API.
    """
    radius_meters = int(request.radius_miles * 1609.34)

    if radius_meters > 50000:
        radius_meters = 50000

    if not settings.MAPBOX_ACCESS_TOKEN:
        logger.error("Mapbox access token not configured")
        raise HTTPException(
            status_code=503,
            detail="POI search not available. Please set MAPBOX_ACCESS_TOKEN in Railway environment variables."
        )

    try:
        logger.info(f"Fetching POIs for ({request.latitude}, {request.longitude}) within {radius_meters}m")
        from app.services.mapbox_places import fetch_mapbox_pois
        mapbox_result = await fetch_mapbox_pois(
            latitude=request.latitude,
            longitude=request.longitude,
            radius_meters=radius_meters,
        )

        from app.services.places import POI
        pois = [
            POI(
                place_id=poi.mapbox_id,
                name=poi.name,
                category=poi.category,
                types=[poi.poi_category] if poi.poi_category else [],
                latitude=poi.latitude,
                longitude=poi.longitude,
                address=poi.full_address or poi.address,
                rating=None,
                user_ratings_total=None,
            )
            for poi in mapbox_result.pois
        ]

        result = TradeAreaAnalysis(
            center_latitude=mapbox_result.center_latitude,
            center_longitude=mapbox_result.center_longitude,
            radius_meters=mapbox_result.radius_meters,
            pois=pois,
            summary=mapbox_result.summary,
        )

        logger.info(f"POI search complete: {len(pois)} POIs found, summary: {result.summary}")
        return result

    except ValueError as e:
        logger.error(f"POI search configuration error: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"POI search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing trade area: {str(e)}")


# =============================================================================
# API Key Checks
# =============================================================================

@router.get("/check-keys/")
async def check_all_api_keys():
    """Check configuration status of all API keys in one request."""
    keys = {
        "google_places": settings.GOOGLE_PLACES_API_KEY is not None,
        "arcgis": settings.ARCGIS_API_KEY is not None,
        "streetlight": settings.STREETLIGHT_API_KEY is not None,
        "reportall": settings.REPORTALL_API_KEY is not None,
        "attom": settings.ATTOM_API_KEY is not None,
        "mapbox": settings.MAPBOX_ACCESS_TOKEN is not None,
        "tavily": settings.TAVILY_API_KEY is not None,
        "crexi": settings.CREXI_API_KEY is not None,
    }
    return {
        "keys": keys,
        "all_configured": all(keys.values()),
        "configured_count": sum(1 for v in keys.values() if v),
        "total_count": len(keys),
    }


# Legacy individual check endpoints (kept for backwards compatibility)
@router.get("/check-api-key/")
async def check_places_api_key():
    """Check if the Google Places API key is configured."""
    return {
        "configured": settings.GOOGLE_PLACES_API_KEY is not None,
        "message": "API key configured" if settings.GOOGLE_PLACES_API_KEY else "API key not set"
    }


# =============================================================================
# Demographics (ArcGIS GeoEnrichment)
# =============================================================================

class DemographicsRequest(BaseModel):
    """Request model for demographics analysis."""
    latitude: float
    longitude: float


@router.post("/demographics/", response_model=DemographicsResponse)
async def get_demographics(request: DemographicsRequest):
    """
    Get demographic data from ArcGIS GeoEnrichment API.

    Returns population, income, employment, and consumer spending data
    for 1-mile, 3-mile, and 5-mile radii around the specified location.
    """
    if not settings.ARCGIS_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ArcGIS API key not configured. Please set ARCGIS_API_KEY environment variable."
        )

    try:
        result = await fetch_demographics(
            latitude=request.latitude,
            longitude=request.longitude,
            radii_miles=[1, 3, 5]
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching demographics: {str(e)}")


@router.get("/check-arcgis-key/")
async def check_arcgis_api_key():
    """Check if the ArcGIS API key is configured."""
    return {
        "configured": settings.ARCGIS_API_KEY is not None,
        "message": "ArcGIS API key configured" if settings.ARCGIS_API_KEY else "ArcGIS API key not set"
    }


# =============================================================================
# Streetlight Traffic Counts
# =============================================================================

class TrafficCountsRequest(BaseModel):
    """Request model for traffic counts analysis."""
    latitude: float
    longitude: float
    radius_miles: float = 1.0
    include_demographics: bool = True
    include_vehicle_attributes: bool = False
    year: Optional[int] = None
    month: Optional[int] = None
    road_classes: Optional[list[str]] = None  # OSM types, default: major roads


class SegmentCountRequest(BaseModel):
    """Request model for segment count estimation."""
    latitude: float
    longitude: float
    radius_miles: float = 1.0
    road_classes: Optional[list[str]] = None  # OSM types, default: major roads


@router.post("/traffic-counts/", response_model=TrafficAnalysis)
async def get_traffic_counts(request: TrafficCountsRequest):
    """
    Get traffic count data from Streetlight Advanced Traffic Counts API.

    **IMPORTANT:** This is a billable endpoint. Use /traffic-counts/estimate/ first.
    """
    if not settings.STREETLIGHT_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Streetlight API key not configured. Please set STREETLIGHT_API_KEY environment variable."
        )

    try:
        result = await fetch_traffic_counts(
            latitude=request.latitude,
            longitude=request.longitude,
            radius_miles=request.radius_miles,
            include_demographics=request.include_demographics,
            include_vehicle_attributes=request.include_vehicle_attributes,
            year=request.year,
            month=request.month,
            road_classes=request.road_classes,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Error fetching traffic counts")
        raise HTTPException(status_code=500, detail=f"Error fetching traffic counts: {str(e)}")


@router.post("/traffic-counts/estimate/", response_model=SegmentCountEstimate)
async def estimate_traffic_segments(request: SegmentCountRequest):
    """
    Estimate the number of road segments in a radius (for quota planning).
    This is a non-billable endpoint.
    """
    if not settings.STREETLIGHT_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Streetlight API key not configured. Please set STREETLIGHT_API_KEY environment variable."
        )

    try:
        client = StreetlightClient()
        result = await client.estimate_segment_count(
            latitude=request.latitude,
            longitude=request.longitude,
            radius_miles=request.radius_miles,
            road_classes=request.road_classes,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Error estimating traffic segments")
        raise HTTPException(status_code=500, detail=f"Error estimating segments: {str(e)}")


@router.get("/check-streetlight-key/")
async def check_streetlight_api_key():
    """Check if the Streetlight API key is configured."""
    return {
        "configured": settings.STREETLIGHT_API_KEY is not None,
        "message": "Streetlight API key configured" if settings.STREETLIGHT_API_KEY else "Streetlight API key not set"
    }


@router.get("/traffic-counts/usage/")
async def get_streetlight_usage():
    """
    Get StreetLight API segment quota usage.
    Non-billable endpoint for monitoring remaining quota.
    """
    if not settings.STREETLIGHT_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Streetlight API key not configured."
        )

    try:
        client = StreetlightClient()
        url = f"{client.base_url}/usage"

        # Scope to trial period (started Feb 10, 2026, expires Mar 10, 2026)
        params = {"term_start": "2026-02-10T00:00:00.000Z"}

        async with httpx.AsyncClient() as http:
            response = await http.get(
                url, headers=client.headers, params=params, timeout=30
            )
            response.raise_for_status()
            data = response.json()

        # Sum up billable segments from all jobs
        total_used = 0
        jobs = data.get("jobs", [])
        for job in jobs:
            if job.get("is_billable", False):
                total_used += job.get("segments_queried", 0)

        return {
            "total_quota": 1000,  # Trial quota (expires Mar 10, 2026)
            "segments_used": total_used,
            "segments_remaining": max(0, 1000 - total_used),
            "job_count": len(jobs),
        }
    except httpx.HTTPStatusError as e:
        logger.error(f"StreetLight usage API error: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch usage data from StreetLight")
    except Exception as e:
        logger.exception("Error fetching StreetLight usage")
        raise HTTPException(status_code=500, detail=f"Error fetching usage: {str(e)}")


# =============================================================================
# Mapbox POI Search (Proof of Concept)
# =============================================================================

from app.services.mapbox_places import (
    fetch_mapbox_pois,
    check_mapbox_token,
    MapboxTradeAreaAnalysis,
)


class MapboxTradeAreaRequest(BaseModel):
    """Request model for Mapbox trade area analysis."""
    latitude: float
    longitude: float
    radius_miles: float = 1.0
    categories: Optional[list[str]] = None


@router.post("/mapbox-trade-area/", response_model=MapboxTradeAreaAnalysis)
async def analyze_trade_area_mapbox(request: MapboxTradeAreaRequest):
    """
    [POC] Analyze trade area using Mapbox Search Box API.

    Key benefits over Google Places:
    - Fewer API calls (1-4 vs 28)
    - Lower cost per analysis
    - Session-based pricing
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured. Set MAPBOX_ACCESS_TOKEN environment variable."
        )

    radius_meters = int(request.radius_miles * 1609.34)

    try:
        result = await fetch_mapbox_pois(
            latitude=request.latitude,
            longitude=request.longitude,
            radius_meters=radius_meters,
            categories=request.categories,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing trade area: {str(e)}")


@router.get("/check-mapbox-token/")
async def check_mapbox_token_endpoint():
    """Check if the Mapbox access token is configured and valid."""
    return await check_mapbox_token()


# =============================================================================
# Store Re-Geocoding
# =============================================================================

async def geocode_address_google(address: str, api_key: str) -> tuple[float, float] | None:
    """Geocode an address using Google Geocoding API."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data["status"] == "OK" and data["results"]:
                location = data["results"][0]["geometry"]["location"]
                return (location["lat"], location["lng"])
            return None
        except Exception:
            return None


async def run_regeocode_task():
    """Background task to re-geocode all stores."""
    global regeocode_status

    api_key = settings.GOOGLE_PLACES_API_KEY
    if not api_key:
        regeocode_status["message"] = "No API key configured"
        regeocode_status["running"] = False
        return

    regeocode_status["running"] = True
    regeocode_status["message"] = "Fetching stores..."

    db = next(get_db())

    try:
        result = db.execute(text("""
            SELECT id, street, city, state, postal_code, latitude, longitude
            FROM stores ORDER BY id
        """))
        stores = result.fetchall()

        regeocode_status["total"] = len(stores)
        regeocode_status["updated"] = 0
        regeocode_status["failed"] = 0

        for i, store in enumerate(stores):
            store_id, street, city, state, postal_code, old_lat, old_lng = store

            regeocode_status["progress"] = i + 1
            regeocode_status["message"] = f"Processing store {i+1}/{len(stores)}"

            parts = [p for p in [street, city, state, postal_code] if p]
            if not parts:
                regeocode_status["failed"] += 1
                continue

            address = ", ".join(parts) + ", USA"

            coords = await geocode_address_google(address, api_key)

            if coords:
                new_lat, new_lng = coords
                db.execute(text("""
                    UPDATE stores
                    SET latitude = :lat,
                        longitude = :lng
                    WHERE id = :id
                """), {"lat": new_lat, "lng": new_lng, "id": store_id})
                regeocode_status["updated"] += 1
            else:
                regeocode_status["failed"] += 1

            await asyncio.sleep(0.05)

            if (i + 1) % 50 == 0:
                db.commit()

        db.commit()
        regeocode_status["message"] = f"Complete! Updated {regeocode_status['updated']}, failed {regeocode_status['failed']}"

    except Exception as e:
        db.rollback()
        regeocode_status["message"] = f"Error: {str(e)}"
    finally:
        regeocode_status["running"] = False
        db.close()


@router.post("/regeocode-stores/")
async def start_regeocode(background_tasks: BackgroundTasks):
    """Start re-geocoding all stores using Google Geocoding API (background task)."""
    global regeocode_status

    if not settings.GOOGLE_PLACES_API_KEY:
        raise HTTPException(status_code=503, detail="Google API key not configured")

    if regeocode_status["running"]:
        raise HTTPException(status_code=409, detail="Re-geocoding already in progress")

    regeocode_status = {
        "running": True,
        "progress": 0,
        "total": 0,
        "updated": 0,
        "failed": 0,
        "message": "Starting..."
    }

    background_tasks.add_task(run_regeocode_task)

    return {"message": "Re-geocoding started. Check /regeocode-status/ for progress."}


@router.get("/regeocode-status/")
async def get_regeocode_status():
    """Get the current status of the re-geocoding task."""
    return regeocode_status


# =============================================================================
# Store Coordinate Validation
# =============================================================================

US_BOUNDS = {
    "min_lat": 24.0,
    "max_lat": 49.5,
    "min_lng": -125.0,
    "max_lng": -66.0,
}


class ValidationResult(BaseModel):
    """Result of store coordinate validation."""
    total_checked: int
    null_coords: int
    zero_coords: int
    out_of_bounds: int
    issues: list[dict]


@router.get("/validate-store-coords/", response_model=ValidationResult)
async def validate_store_coordinates(
    brand: Optional[str] = Query(None, description="Filter by brand"),
    limit: int = Query(1000, description="Max stores to check"),
):
    """
    Validate store coordinates to identify problematic geocoding data.

    Checks for null coordinates, zero coordinates (0, 0), and
    coordinates outside continental US bounds.
    """
    db = next(get_db())
    try:
        query_str = """
            SELECT id, brand, street, city, state, latitude, longitude
            FROM stores
        """
        params = {"limit": limit}

        if brand:
            query_str += " WHERE brand = :brand"
            params["brand"] = brand.lower()

        query_str += " ORDER BY id LIMIT :limit"

        result = db.execute(text(query_str), params)
        stores = result.fetchall()

        null_coords = []
        zero_coords = []
        out_of_bounds = []

        for store in stores:
            store_id, store_brand, street, city, state, lat, lng = store

            if lat is None or lng is None:
                null_coords.append({
                    "id": store_id,
                    "brand": store_brand,
                    "address": f"{street}, {city}, {state}" if street else f"{city}, {state}",
                    "issue": "NULL_COORDS",
                })
                continue

            if lat == 0 and lng == 0:
                zero_coords.append({
                    "id": store_id,
                    "brand": store_brand,
                    "address": f"{street}, {city}, {state}" if street else f"{city}, {state}",
                    "issue": "ZERO_COORDS",
                })
                continue

            if not (US_BOUNDS["min_lat"] <= lat <= US_BOUNDS["max_lat"]) or \
               not (US_BOUNDS["min_lng"] <= lng <= US_BOUNDS["max_lng"]):
                out_of_bounds.append({
                    "id": store_id,
                    "brand": store_brand,
                    "lat": lat,
                    "lng": lng,
                    "issue": "OUT_OF_BOUNDS",
                })

        all_issues = null_coords + zero_coords + out_of_bounds

        return ValidationResult(
            total_checked=len(stores),
            null_coords=len(null_coords),
            zero_coords=len(zero_coords),
            out_of_bounds=len(out_of_bounds),
            issues=all_issues[:50],
        )

    except Exception as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")
    finally:
        db.close()
