"""
Matrix & Isochrone API endpoints.

Includes:
- Mapbox Matrix API (drive-time/distance calculations)
- Competitor accessibility analysis
- Matrix cache management
- Isochrone (drive-time polygon) endpoints
"""
import httpx
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text

from app.services.mapbox_matrix import (
    MatrixRequest,
    MatrixResponse,
    MatrixElement,
    CompetitorAccessResult,
    TravelProfile,
    calculate_matrix,
    calculate_matrix_batched,
    analyze_competitor_access,
    get_cache_stats,
    clear_matrix_cache,
)
from app.services.mapbox_isochrone import (
    IsochroneRequest as IsochroneServiceRequest,
    IsochroneResponse,
    IsochroneProfile,
    fetch_isochrone,
    fetch_multi_contour_isochrone,
    DEFAULT_ISOCHRONE_COLORS,
)
from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


# =============================================================================
# Matrix API Endpoints (Drive-Time Analysis)
# =============================================================================

class MatrixRequestBody(BaseModel):
    """Request body for matrix calculation."""
    origins: list[list[float]]  # [[lng, lat], ...]
    destinations: list[list[float]]  # [[lng, lat], ...]
    profile: str = "driving"


class CompetitorAccessRequest(BaseModel):
    """Request body for competitor access analysis."""
    site_latitude: float
    site_longitude: float
    competitor_ids: Optional[list[int]] = None
    max_competitors: int = 25
    profile: str = "driving-traffic"


@router.post("/matrix/", response_model=MatrixResponse)
async def calculate_travel_matrix(request: MatrixRequestBody):
    """
    Calculate travel time/distance matrix between origins and destinations.

    Uses Mapbox Matrix API. Results are cached for 24 hours.

    **Limits:** Maximum 25 origins x 25 destinations per request.
    For larger datasets, use /matrix/batched endpoint.

    **Profiles:** driving, driving-traffic, walking, cycling
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    origins = [(coord[0], coord[1]) for coord in request.origins]
    destinations = [(coord[0], coord[1]) for coord in request.destinations]

    try:
        profile = TravelProfile(request.profile)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid profile: {request.profile}. Valid options: driving, driving-traffic, walking, cycling"
        )

    try:
        result = await calculate_matrix(
            origins=origins,
            destinations=destinations,
            profile=profile,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Mapbox API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matrix calculation error: {str(e)}")


@router.post("/matrix/batched/", response_model=MatrixResponse)
async def calculate_travel_matrix_batched(request: MatrixRequestBody):
    """
    Calculate travel matrix for large datasets with automatic batching.

    Unlike /matrix/, this endpoint can handle datasets larger than 25x25 by
    automatically splitting into multiple API calls and combining results.
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    origins = [(coord[0], coord[1]) for coord in request.origins]
    destinations = [(coord[0], coord[1]) for coord in request.destinations]

    try:
        profile = TravelProfile(request.profile)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid profile: {request.profile}"
        )

    try:
        result = await calculate_matrix_batched(
            origins=origins,
            destinations=destinations,
            profile=profile,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batched matrix error: {str(e)}")


@router.post("/competitor-access/", response_model=CompetitorAccessResult)
async def analyze_competitor_accessibility(request: CompetitorAccessRequest):
    """
    Analyze drive times from a potential site to nearby competitors.

    Returns competitors sorted by travel time.

    **Parameters:**
    - `site_latitude`, `site_longitude`: Candidate site location
    - `competitor_ids`: Specific stores to analyze (optional)
    - `max_competitors`: Maximum competitors (default 25)
    - `profile`: Travel profile (default: driving-traffic)
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    try:
        profile = TravelProfile(request.profile)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid profile: {request.profile}"
        )

    # Fetch competitors from database
    db = next(get_db())
    try:
        if request.competitor_ids:
            query = text("""
                SELECT id, brand, street, city, state, postal_code, latitude, longitude
                FROM stores
                WHERE id = ANY(:ids)
                AND latitude IS NOT NULL
                AND longitude IS NOT NULL
            """)
            result = db.execute(query, {"ids": request.competitor_ids})
        else:
            query = text("""
                SELECT id, brand, street, city, state, postal_code, latitude, longitude,
                       (
                           3959 * acos(
                               LEAST(1.0, GREATEST(-1.0,
                                   cos(radians(:lat)) * cos(radians(latitude)) *
                                   cos(radians(longitude) - radians(:lng)) +
                                   sin(radians(:lat)) * sin(radians(latitude))
                               ))
                           )
                       ) as distance_miles
                FROM stores
                WHERE latitude IS NOT NULL
                AND longitude IS NOT NULL
                ORDER BY distance_miles
                LIMIT :limit
            """)
            result = db.execute(query, {
                "lat": request.site_latitude,
                "lng": request.site_longitude,
                "limit": request.max_competitors,
            })

        competitors = [
            {
                "id": row[0],
                "brand": row[1],
                "street": row[2],
                "city": row[3],
                "state": row[4],
                "postal_code": row[5],
                "latitude": row[6],
                "longitude": row[7],
            }
            for row in result.fetchall()
        ]
    except Exception as db_error:
        logger.error(f"Database error in competitor-access: {db_error}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
    finally:
        db.close()

    if not competitors:
        return CompetitorAccessResult(
            site_latitude=request.site_latitude,
            site_longitude=request.site_longitude,
            competitors=[],
            profile=request.profile,
        )

    # Try with requested number of competitors, retry with fewer if Mapbox fails
    max_retries = 5
    current_max = request.max_competitors
    last_error = None

    for attempt in range(max_retries):
        try:
            limited_competitors = competitors[:current_max]

            access_result = await analyze_competitor_access(
                site_location=(request.site_longitude, request.site_latitude),
                competitor_locations=limited_competitors,
                profile=profile,
                max_competitors=current_max,
            )
            return access_result
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 422 and attempt < max_retries - 1:
                old_max = current_max
                current_max = max(3, current_max // 2)
                logger.warning(f"Mapbox 422 error, retrying with {current_max} competitors (was {old_max})")
                continue
            logger.error(f"Mapbox Matrix API error: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=f"Travel time service error: {e.response.status_code}. Please try again."
            )
        except httpx.RequestError as e:
            logger.error(f"Mapbox Matrix API connection error: {e}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="Unable to connect to travel time service. Please try again."
            )
        except ValueError as e:
            logger.error(f"Competitor access validation error: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Competitor access error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Competitor access error: {str(e)}")

    if last_error:
        raise HTTPException(
            status_code=502,
            detail=f"Travel time service error after {max_retries} attempts. Please try again."
        )


@router.get("/matrix/cache-stats/")
async def get_matrix_cache_statistics():
    """Get Matrix API cache statistics."""
    return get_cache_stats()


@router.post("/matrix/clear-cache/")
async def clear_matrix_cache_endpoint():
    """Clear the Matrix API cache."""
    clear_matrix_cache()
    return {"status": "success", "message": "Matrix cache cleared"}


# =============================================================================
# Isochrone API Endpoints (Drive-Time Polygons)
# =============================================================================

class IsochroneRequestBody(BaseModel):
    """Request body for isochrone calculation."""
    latitude: float
    longitude: float
    minutes: int = 10
    profile: str = "driving"


class MultiContourIsochroneRequest(BaseModel):
    """Request body for multi-contour isochrone."""
    latitude: float
    longitude: float
    minutes_list: list[int] = [5, 10, 15]
    profile: str = "driving"
    colors: Optional[list[str]] = None


@router.post("/isochrone/", response_model=IsochroneResponse)
async def get_isochrone_endpoint(request: IsochroneRequestBody):
    """
    Get a drive-time isochrone polygon.

    Returns a GeoJSON polygon showing the area reachable within the specified
    travel time from the center point.

    **Parameters:**
    - `latitude`, `longitude`: Center point coordinates
    - `minutes`: Travel time in minutes (1-60)
    - `profile`: Travel profile (driving, driving-traffic, walking, cycling)
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    try:
        profile = IsochroneProfile(request.profile)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid profile: {request.profile}. Valid options: driving, driving-traffic, walking, cycling"
        )

    if request.minutes < 1 or request.minutes > 60:
        raise HTTPException(
            status_code=400,
            detail="Minutes must be between 1 and 60"
        )

    try:
        result = await fetch_isochrone(
            latitude=request.latitude,
            longitude=request.longitude,
            minutes=request.minutes,
            profile=profile,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Isochrone error: {str(e)}")


@router.post("/isochrone/multi/", response_model=IsochroneResponse)
async def get_multi_contour_isochrone_endpoint(request: MultiContourIsochroneRequest):
    """
    Get multiple isochrone contours in a single request.

    Returns multiple concentric polygons showing areas reachable at different
    travel times (e.g., 5, 10, 15 minutes).

    **Parameters:**
    - `latitude`, `longitude`: Center point coordinates
    - `minutes_list`: List of travel times (max 4 contours)
    - `profile`: Travel profile
    - `colors`: Optional hex colors for each contour
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    try:
        profile = IsochroneProfile(request.profile)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid profile: {request.profile}"
        )

    if len(request.minutes_list) > 4:
        raise HTTPException(
            status_code=400,
            detail="Maximum 4 contours allowed"
        )

    colors = request.colors or DEFAULT_ISOCHRONE_COLORS[:len(request.minutes_list)]

    try:
        result = await fetch_multi_contour_isochrone(
            latitude=request.latitude,
            longitude=request.longitude,
            minutes_list=request.minutes_list,
            profile=profile,
            colors=colors,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-contour isochrone error: {str(e)}")
