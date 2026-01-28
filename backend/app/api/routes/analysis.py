"""
Analysis API endpoints for trade area analysis and POI lookup.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.services.places import fetch_nearby_pois, TradeAreaAnalysis
from app.core.config import settings

router = APIRouter(prefix="/analysis", tags=["analysis"])


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
