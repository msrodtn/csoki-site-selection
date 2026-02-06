"""
Property & Parcel API endpoints.

Includes:
- ReportAll parcel lookup
- Legacy AI-powered property search (Tavily/OpenAI)
- ATTOM property search (radius + bounds)
"""
import httpx
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.property_search import (
    search_properties,
    PropertySearchResult,
    MapBounds,
    check_api_keys as check_property_api_keys,
)
from app.services.attom import (
    search_properties_by_radius as attom_search_radius,
    search_properties_by_bounds as attom_search_bounds,
    check_attom_api_key,
    PropertySearchResult as ATTOMPropertySearchResult,
    GeoBounds as ATTOMGeoBounds,
    PropertyType as ATTOMPropertyType,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


# =============================================================================
# Parcel Lookup (ReportAll)
# =============================================================================

class ParcelRequest(BaseModel):
    """Request model for parcel lookup."""
    latitude: float
    longitude: float


class ParcelInfo(BaseModel):
    """Response model for parcel information."""
    parcel_id: Optional[str] = None
    owner: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    acreage: Optional[float] = None
    land_value: Optional[float] = None
    building_value: Optional[float] = None
    total_value: Optional[float] = None
    land_use: Optional[str] = None
    zoning: Optional[str] = None
    year_built: Optional[int] = None
    building_sqft: Optional[float] = None
    sale_price: Optional[float] = None
    sale_date: Optional[str] = None
    latitude: float
    longitude: float
    geometry: Optional[str] = None  # WKT geometry for boundary highlighting
    raw_data: Optional[dict] = None  # Full response for debugging


@router.post("/parcel/", response_model=ParcelInfo)
async def get_parcel_info(request: ParcelRequest):
    """
    Get parcel information from ReportAll API.

    Returns property details including owner, acreage, zoning, and values
    for the parcel at the specified location.

    - **latitude**: Point latitude
    - **longitude**: Point longitude
    """
    if not settings.REPORTALL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ReportAll API key not configured. Please set REPORTALL_API_KEY environment variable."
        )

    # ReportAll uses POINT(lon lat) format (longitude first!)
    point_wkt = f"POINT({request.longitude} {request.latitude})"

    url = "https://reportallusa.com/api/parcels"
    params = {
        "client": settings.REPORTALL_API_KEY,
        "v": "9",
        "spatial_intersect": point_wkt,
        "si_srid": "4326"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not data:
                raise HTTPException(
                    status_code=404,
                    detail="No parcel found at this location"
                )

            results = data.get("results", []) if isinstance(data, dict) else data

            if not results or len(results) == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No parcel found at this location"
                )

            parcel = results[0] if isinstance(results, list) else results

            def get_field(*keys, default=None):
                for key in keys:
                    if key in parcel and parcel[key] is not None:
                        return parcel[key]
                return default

            return ParcelInfo(
                parcel_id=get_field("parcel_id", "robust_id", "apn", "pin"),
                owner=get_field("owner", "owner_surname", "owner_name"),
                address=get_field("address", "addr_number", "situs_address"),
                city=get_field("addr_city", "city", "situs_city"),
                state=get_field("addr_state", "state", "situs_state"),
                zip_code=get_field("addr_zip", "zip", "situs_zip"),
                acreage=get_field("acreage_deeded", "acreage_calc", "acres", "acreage"),
                land_value=get_field("mkt_val_land", "land_value", "assessed_land"),
                building_value=get_field("mkt_val_bldg", "building_value", "impr_value"),
                total_value=get_field("mkt_val_tot", "total_value", "market_value", "assessed_total"),
                land_use=get_field("land_use_class", "land_use_code", "land_use", "use_code"),
                zoning=get_field("zoning", "zone", "zoning_code"),
                year_built=get_field("year_built", "yr_built"),
                building_sqft=get_field("bldg_sqft", "building_sqft", "sqft", "living_area"),
                sale_price=get_field("sale_price", "trans_price", "last_sale_price"),
                sale_date=get_field("trans_date", "sale_date", "deed_date"),
                latitude=request.latitude,
                longitude=request.longitude,
                geometry=get_field("geom_as_wkt", "geom", "geometry", "wkt", "the_geom", "ll_geom", "shape", "shape_wkt", "wkt_geom", "polygon"),
                raw_data=parcel
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again in a moment."
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"ReportAll API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to ReportAll API: {str(e)}"
            )


@router.get("/check-reportall-key/")
async def check_reportall_api_key():
    """Check if the ReportAll API key is configured."""
    return {
        "configured": settings.REPORTALL_API_KEY is not None,
        "message": "ReportAll API key configured" if settings.REPORTALL_API_KEY else "ReportAll API key not set"
    }


# =============================================================================
# Property Search (AI-powered CRE listings - Legacy)
# =============================================================================

class PropertySearchBounds(BaseModel):
    """Map viewport bounds for filtering."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


class PropertySearchRequest(BaseModel):
    """Request model for property search."""
    latitude: float
    longitude: float
    radius_miles: float = 5.0
    property_types: Optional[list[str]] = None
    bounds: Optional[PropertySearchBounds] = None


@router.post("/property-search/", response_model=PropertySearchResult)
async def search_properties_endpoint(request: PropertySearchRequest):
    """
    Search for commercial properties for sale near a location.

    Uses AI-powered web search to find listings from multiple sources
    (Crexi, LoopNet, Zillow Commercial, etc.) and returns structured data.

    Note: Requires TAVILY_API_KEY and OPENAI_API_KEY or ANTHROPIC_API_KEY.
    """
    if not settings.TAVILY_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
        )

    if not settings.ANTHROPIC_API_KEY and not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="No AI API key configured. Please set ANTHROPIC_API_KEY (recommended) or OPENAI_API_KEY environment variable."
        )

    try:
        service_bounds = None
        if request.bounds:
            service_bounds = MapBounds(
                min_lat=request.bounds.min_lat,
                max_lat=request.bounds.max_lat,
                min_lng=request.bounds.min_lng,
                max_lng=request.bounds.max_lng,
            )

        result = await search_properties(
            latitude=request.latitude,
            longitude=request.longitude,
            radius_miles=request.radius_miles,
            property_types=request.property_types,
            bounds=service_bounds,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching properties: {str(e)}")


@router.get("/check-property-search-keys/")
async def check_property_search_api_keys():
    """Check which API keys are configured for property search."""
    return await check_property_api_keys()


# =============================================================================
# ATTOM-Powered Property Search
# =============================================================================

class ATTOMSearchRequest(BaseModel):
    """Request model for ATTOM property search."""
    latitude: float
    longitude: float
    radius_miles: float = 5.0
    property_types: Optional[list[str]] = None
    min_opportunity_score: float = 0
    limit: int = 50


class ATTOMBoundsSearchRequest(BaseModel):
    """Request model for ATTOM property search by map bounds."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float
    property_types: Optional[list[str]] = None
    min_opportunity_score: float = 0
    limit: int = 50


@router.post("/properties/search/", response_model=ATTOMPropertySearchResult)
async def search_attom_properties(request: ATTOMSearchRequest):
    """
    Search for commercial properties using ATTOM Property API.

    Returns properties with opportunity signals (likelihood to sell indicators).
    """
    if not settings.ATTOM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ATTOM API key not configured. Please set ATTOM_API_KEY environment variable."
        )

    prop_types = None
    if request.property_types:
        prop_types = []
        for pt in request.property_types:
            try:
                prop_types.append(ATTOMPropertyType(pt.lower()))
            except ValueError:
                pass

    try:
        result = await attom_search_radius(
            latitude=request.latitude,
            longitude=request.longitude,
            radius_miles=request.radius_miles,
            property_types=prop_types,
            min_opportunity_score=request.min_opportunity_score,
            limit=request.limit,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching properties: {str(e)}")


@router.post("/properties/search-bounds/", response_model=ATTOMPropertySearchResult)
async def search_attom_properties_by_bounds(request: ATTOMBoundsSearchRequest):
    """
    Search for commercial properties within map viewport bounds.

    Same as /properties/search/ but uses bounding box instead of radius.
    """
    if not settings.ATTOM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ATTOM API key not configured. Please set ATTOM_API_KEY environment variable."
        )

    bounds = ATTOMGeoBounds(
        min_lat=request.min_lat,
        max_lat=request.max_lat,
        min_lng=request.min_lng,
        max_lng=request.max_lng,
    )

    prop_types = None
    if request.property_types:
        prop_types = []
        for pt in request.property_types:
            try:
                prop_types.append(ATTOMPropertyType(pt.lower()))
            except ValueError:
                pass

    try:
        result = await attom_search_bounds(
            bounds=bounds,
            property_types=prop_types,
            min_opportunity_score=request.min_opportunity_score,
            limit=request.limit,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching properties: {str(e)}")


@router.get("/check-attom-key/")
async def check_attom_api_key_endpoint():
    """Check if the ATTOM API key is configured and valid."""
    return await check_attom_api_key()
