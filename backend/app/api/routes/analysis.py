"""
Analysis API endpoints for trade area analysis and POI lookup.
"""
import asyncio
import httpx
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text

from app.services.places import fetch_nearby_pois, TradeAreaAnalysis
from app.services.arcgis import fetch_demographics, DemographicsResponse
from app.core.config import settings
from app.core.database import get_db

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


class TradeAreaRequest(BaseModel):
    """Request model for trade area analysis."""
    latitude: float
    longitude: float
    radius_miles: float = 1.0  # Default 1 mile radius


@router.post("/trade-area/", response_model=TradeAreaAnalysis)
async def analyze_trade_area(request: TradeAreaRequest):
    """
    Analyze the trade area around a location.

    Fetches nearby points of interest (POIs) within the specified radius
    and categorizes them into: anchors, quick_service, restaurants, retail.

    - **latitude**: Center point latitude
    - **longitude**: Center point longitude
    - **radius_miles**: Search radius in miles (default: 1.0)
    """
    if not settings.GOOGLE_PLACES_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Google Places API key not configured. Please set GOOGLE_PLACES_API_KEY environment variable."
        )

    # Convert miles to meters (1 mile = 1609.34 meters)
    radius_meters = int(request.radius_miles * 1609.34)

    # Cap at 50km (Google Places API limit)
    if radius_meters > 50000:
        radius_meters = 50000

    try:
        result = await fetch_nearby_pois(
            latitude=request.latitude,
            longitude=request.longitude,
            radius_meters=radius_meters,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing trade area: {str(e)}")


@router.get("/check-api-key/")
async def check_places_api_key():
    """
    Check if the Google Places API key is configured.
    """
    return {
        "configured": settings.GOOGLE_PLACES_API_KEY is not None,
        "message": "API key configured" if settings.GOOGLE_PLACES_API_KEY else "API key not set"
    }


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

    - **latitude**: Center point latitude
    - **longitude**: Center point longitude
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
    """
    Check if the ArcGIS API key is configured.
    """
    return {
        "configured": settings.ARCGIS_API_KEY is not None,
        "message": "ArcGIS API key configured" if settings.ARCGIS_API_KEY else "ArcGIS API key not set"
    }


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
        # Fetch all stores
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

            # Build address
            parts = [p for p in [street, city, state, postal_code] if p]
            if not parts:
                regeocode_status["failed"] += 1
                continue

            address = ", ".join(parts) + ", USA"

            # Geocode
            coords = await geocode_address_google(address, api_key)

            if coords:
                new_lat, new_lng = coords
                # Only update latitude/longitude - PostGIS location column may not exist
                db.execute(text("""
                    UPDATE stores
                    SET latitude = :lat,
                        longitude = :lng
                    WHERE id = :id
                """), {"lat": new_lat, "lng": new_lng, "id": store_id})
                regeocode_status["updated"] += 1
            else:
                regeocode_status["failed"] += 1

            # Rate limiting
            await asyncio.sleep(0.05)

            # Commit every 50 stores
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
    """
    Start re-geocoding all stores using Google Geocoding API.
    This runs in the background - check /regeocode-status/ for progress.
    """
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
