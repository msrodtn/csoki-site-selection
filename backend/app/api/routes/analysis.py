"""
Analysis API endpoints for trade area analysis and POI lookup.
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
from app.services.property_search import search_properties, PropertySearchResult, MapBounds, check_api_keys as check_property_api_keys
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

    - **latitude**: Center point latitude
    - **longitude**: Center point longitude
    - **radius_miles**: Search radius in miles (default: 1.0)
    """
    # Convert miles to meters (1 mile = 1609.34 meters)
    radius_meters = int(request.radius_miles * 1609.34)

    # Cap at 50km
    if radius_meters > 50000:
        radius_meters = 50000

    # Check Mapbox token
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

        # Convert Mapbox response to TradeAreaAnalysis format
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


# =============================================================================
# Streetlight Traffic Counts Endpoints
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


class SegmentCountRequest(BaseModel):
    """Request model for segment count estimation."""
    latitude: float
    longitude: float
    radius_miles: float = 1.0


@router.post("/traffic-counts/", response_model=TrafficAnalysis)
async def get_traffic_counts(request: TrafficCountsRequest):
    """
    Get traffic count data from Streetlight Advanced Traffic Counts API.

    Returns AADT (Annual Average Daily Traffic), speed metrics, and optionally
    traveler demographics (income, trip purpose) and vehicle attributes
    (body class, power train) for road segments within the specified radius.

    **IMPORTANT:** This is a billable endpoint. Quota is charged based on:
    - Number of road segments in the radius
    - Number of date periods requested (months)

    Use the /traffic-counts/estimate/ endpoint first to preview quota usage.

    - **latitude**: Center point latitude
    - **longitude**: Center point longitude
    - **radius_miles**: Search radius in miles (0.25-5.0, default: 1.0)
    - **include_demographics**: Include traveler income/trip purpose data
    - **include_vehicle_attributes**: Include vehicle class/powertrain data
    - **year**: Optional year filter (defaults to most recent available)
    - **month**: Optional month filter (1-12)
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

    This is a non-billable endpoint. Use it before calling /traffic-counts/
    to understand the quota impact of your query.

    - **latitude**: Center point latitude
    - **longitude**: Center point longitude
    - **radius_miles**: Search radius in miles (0.25-5.0, default: 1.0)

    Returns:
    - **segment_count**: Number of Streetlight road segments in the area
    - **geometry_type**: Type of geometry used (radius)
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
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Error estimating traffic segments")
        raise HTTPException(status_code=500, detail=f"Error estimating segments: {str(e)}")


@router.get("/check-streetlight-key/")
async def check_streetlight_api_key():
    """
    Check if the Streetlight API key is configured.
    """
    return {
        "configured": settings.STREETLIGHT_API_KEY is not None,
        "message": "Streetlight API key configured" if settings.STREETLIGHT_API_KEY else "Streetlight API key not set"
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

            # ReportAll API returns: { status, count, page, rpp, results: [...], query }
            # The actual parcel data is in the 'results' array
            if not data:
                raise HTTPException(
                    status_code=404,
                    detail="No parcel found at this location"
                )

            # Extract results array from wrapper response
            results = data.get("results", []) if isinstance(data, dict) else data

            if not results or len(results) == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No parcel found at this location"
                )

            # Get the first (most relevant) parcel from results
            parcel = results[0] if isinstance(results, list) else results

            # Extract and normalize fields
            # ReportAll field names vary by county, so we check multiple possible names
            def get_field(*keys, default=None):
                for key in keys:
                    if key in parcel and parcel[key] is not None:
                        return parcel[key]
                return default

            # Map ReportAll fields (based on their official API documentation)
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
                geometry=get_field("geom_as_wkt", "geom", "geometry", "wkt", "the_geom", "ll_geom", "shape", "shape_wkt", "wkt_geom", "polygon"),  # WKT geometry for highlighting
                raw_data=parcel  # Include full response for debugging
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
    """
    Check if the ReportAll API key is configured.
    """
    return {
        "configured": settings.REPORTALL_API_KEY is not None,
        "message": "ReportAll API key configured" if settings.REPORTALL_API_KEY else "ReportAll API key not set"
    }


# ============================================
# Property Search (AI-powered CRE listings)
# ============================================

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
    property_types: Optional[list[str]] = None  # retail, land, office, industrial, mixed_use
    bounds: Optional[PropertySearchBounds] = None  # Map viewport bounds for precise filtering


@router.post("/property-search/", response_model=PropertySearchResult)
async def search_properties_endpoint(request: PropertySearchRequest):
    """
    Search for commercial properties for sale near a location.

    Uses AI-powered web search to find listings from multiple sources
    (Crexi, LoopNet, Zillow Commercial, etc.) and returns structured data.

    - **latitude**: Center point latitude
    - **longitude**: Center point longitude
    - **radius_miles**: Search radius in miles (default: 5.0)
    - **property_types**: Filter by type (retail, land, office, industrial, mixed_use)

    Note: Requires TAVILY_API_KEY and OPENAI_API_KEY to be configured.
    """
    # Check required API keys
    if not settings.TAVILY_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
        )

    # Check for at least one AI provider (prefer Anthropic/Claude)
    if not settings.ANTHROPIC_API_KEY and not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="No AI API key configured. Please set ANTHROPIC_API_KEY (recommended) or OPENAI_API_KEY environment variable."
        )

    try:
        # Convert API bounds to service bounds if provided
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
    """
    Check which API keys are configured for property search.
    """
    return await check_property_api_keys()


@router.get("/debug-property-search/")
async def debug_property_search(location: str = "Davenport, IA", extract: bool = False):
    """
    Debug endpoint to see raw Tavily search results for a location.
    Add ?extract=true to also run AI extraction on the results.
    """
    import httpx
    from openai import AsyncOpenAI
    import json as json_module

    if not settings.TAVILY_API_KEY:
        return {"error": "TAVILY_API_KEY not configured"}

    query = f'"{location}" commercial property for sale listing price address'

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "advanced",
                    "include_raw_content": True,
                    "max_results": 5,
                },
            )

            if response.status_code != 200:
                return {"error": f"Tavily failed: {response.status_code}", "details": response.text}

            data = response.json()
            results = data.get("results", [])

            # Return simplified results for debugging
            debug_results = []
            for r in results:
                title = r.get("title") or ""
                url = r.get("url") or ""
                content = r.get("content") or ""
                raw_content = r.get("raw_content") or ""
                debug_results.append({
                    "title": title[:100],
                    "url": url,
                    "content_preview": content[:500],
                    "has_raw_content": bool(raw_content),
                    "raw_content_length": len(raw_content),
                })

            response_data = {
                "query": query,
                "result_count": len(results),
                "results": debug_results,
            }

            # Optionally run AI extraction to see what it finds
            if extract and settings.OPENAI_API_KEY and results:
                try:
                    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

                    # Build content text like the main function does
                    content_text = ""
                    for i, result in enumerate(results):
                        r_title = result.get('title') or ''
                        r_url = result.get('url') or ''
                        r_content = result.get('content') or ''
                        r_raw = result.get('raw_content') or ''
                        content_text += f"\n--- Result {i+1} ---\n"
                        content_text += f"Title: {r_title}\n"
                        content_text += f"URL: {r_url}\n"
                        content_text += f"Content: {r_content[:1500]}\n"
                        if r_raw:
                            content_text += f"Raw Content: {r_raw[:2000]}\n"

                    prompt = f"""Extract commercial property listings from these search results for {location}.

Look for ANY property that appears to be for sale, including:
- Retail spaces, storefronts, shopping centers
- Office buildings, office space
- Land, lots, development sites
- Industrial, warehouse, distribution centers
- Mixed-use properties

For each property found, extract what you can find:
- address: street address (required - skip if not found)
- city: city name
- state: 2-letter state code
- price: price as shown (e.g., "$500,000", "$15/sqft", "Contact for pricing")
- price_numeric: just the number, null if unavailable
- sqft: square footage as shown
- sqft_numeric: just the number, null if unavailable
- property_type: one of: retail, land, office, industrial, mixed_use
- url: the listing URL
- description: brief description (max 100 chars)

Be generous in extraction - if you see something that looks like a property listing with an address and price, include it.

Return JSON: {{"listings": [...]}}
If no listings found, return: {{"listings": []}}

Search Results:
{content_text}
"""

                    ai_response = await openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a data extraction assistant. Extract structured property listing data from web search results. Return only valid JSON."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1,
                    )

                    ai_content = ai_response.choices[0].message.content
                    ai_data = json_module.loads(ai_content)

                    response_data["ai_extraction"] = {
                        "raw_response": ai_content[:2000],
                        "parsed_listings": ai_data.get("listings", []),
                        "listing_count": len(ai_data.get("listings", []))
                    }
                except Exception as ai_err:
                    response_data["ai_extraction_error"] = str(ai_err)

            return response_data
    except Exception as e:
        return {"error": f"Exception: {str(e)}", "type": str(type(e).__name__)}


# ============================================
# ATTOM-Powered Property Search (New)
# ============================================

from app.services.attom import (
    search_properties_by_radius as attom_search_radius,
    search_properties_by_bounds as attom_search_bounds,
    check_attom_api_key,
    PropertySearchResult as ATTOMPropertySearchResult,
    GeoBounds as ATTOMGeoBounds,
    PropertyType as ATTOMPropertyType,
)


class ATTOMSearchRequest(BaseModel):
    """Request model for ATTOM property search."""
    latitude: float
    longitude: float
    radius_miles: float = 5.0
    property_types: Optional[list[str]] = None  # retail, land, office, industrial, mixed_use
    min_opportunity_score: float = 0  # Filter by minimum opportunity score (0-100)
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
    Unlike active listings, these are properties that show signs of potential sale:
    - Tax delinquency
    - Long-term ownership (estate planning)
    - Foreclosure/pre-foreclosure status
    - Undervalued assessments

    Parameters:
    - **latitude**: Center point latitude
    - **longitude**: Center point longitude
    - **radius_miles**: Search radius in miles (default: 5.0)
    - **property_types**: Filter by type (retail, land, office, industrial, mixed_use)
    - **min_opportunity_score**: Filter by minimum score 0-100 (default: 0)
    - **limit**: Maximum properties to return (default: 50)
    """
    if not settings.ATTOM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ATTOM API key not configured. Please set ATTOM_API_KEY environment variable."
        )

    # Convert string property types to enum
    prop_types = None
    if request.property_types:
        prop_types = []
        for pt in request.property_types:
            try:
                prop_types.append(ATTOMPropertyType(pt.lower()))
            except ValueError:
                pass  # Ignore invalid property types

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
    Ideal for map-based searches where you want to show properties in the current view.
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

    # Convert string property types to enum
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
    """
    Check if the ATTOM API key is configured and valid.
    """
    return await check_attom_api_key()


# ============================================
# Mapbox POI Search (Proof of Concept)
# ============================================

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
    categories: Optional[list[str]] = None  # anchors, quick_service, restaurants, retail


@router.post("/mapbox-trade-area/", response_model=MapboxTradeAreaAnalysis)
async def analyze_trade_area_mapbox(request: MapboxTradeAreaRequest):
    """
    [POC] Analyze trade area using Mapbox Search Box API.

    This is a proof-of-concept alternative to Google Places.
    Key benefits:
    - Fewer API calls (1-4 vs 28 for Google)
    - Lower cost per analysis
    - Session-based pricing

    Parameters:
    - **latitude**: Center point latitude
    - **longitude**: Center point longitude
    - **radius_miles**: Search radius in miles (default: 1.0)
    - **categories**: Optional filter (anchors, quick_service, restaurants, retail)
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured. Set MAPBOX_ACCESS_TOKEN environment variable."
        )

    # Convert miles to meters
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
    """
    Check if the Mapbox access token is configured and valid.
    """
    return await check_mapbox_token()


# =============================================================================
# Matrix API Endpoints (Drive-Time Analysis)
# =============================================================================

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


class MatrixRequestBody(BaseModel):
    """Request body for matrix calculation."""
    origins: list[list[float]]  # [[lng, lat], ...]
    destinations: list[list[float]]  # [[lng, lat], ...]
    profile: str = "driving"


class CompetitorAccessRequest(BaseModel):
    """Request body for competitor access analysis."""
    site_latitude: float
    site_longitude: float
    competitor_ids: Optional[list[int]] = None  # If None, uses nearest competitors
    max_competitors: int = 25
    profile: str = "driving-traffic"


@router.post("/matrix/", response_model=MatrixResponse)
async def calculate_travel_matrix(request: MatrixRequestBody):
    """
    Calculate travel time/distance matrix between origins and destinations.

    Uses Mapbox Matrix API to calculate travel times for all origin-destination pairs.
    Results are cached for 24 hours to reduce API costs.

    **Limits:**
    - Maximum 25 origins × 25 destinations per request (625 elements)
    - For larger datasets, use /matrix/batched endpoint

    **Profiles:**
    - `driving` - Standard driving (default)
    - `driving-traffic` - With real-time traffic
    - `walking` - Walking
    - `cycling` - Cycling

    **Returns:**
    - Duration in seconds for each pair
    - Distance in meters for each pair
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    # Convert to tuples
    origins = [(coord[0], coord[1]) for coord in request.origins]
    destinations = [(coord[0], coord[1]) for coord in request.destinations]

    # Validate profile
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

    Unlike /matrix/, this endpoint can handle datasets larger than 25×25 by
    automatically splitting into multiple API calls and combining results.

    **Use cases:**
    - Analyzing coverage for all stores in a region
    - Market gap analysis with many candidate sites
    - Fleet routing optimization

    **Note:** Larger requests = more API calls = higher cost
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

    Returns competitors sorted by travel time, showing which are most
    accessible from the candidate site location.

    **Use cases:**
    - Identify competition cannibalization risk
    - Understand customer drive-time patterns
    - Validate site selection decisions

    **Parameters:**
    - `site_latitude`, `site_longitude`: Candidate site location
    - `competitor_ids`: Specific stores to analyze (optional)
    - `max_competitors`: Maximum competitors (default 25)
    - `profile`: Travel profile (default: driving-traffic for realistic times)
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
            # Fetch specific competitors
            query = text("""
                SELECT id, brand, street, city, state, postal_code, latitude, longitude
                FROM stores
                WHERE id = ANY(:ids)
                AND latitude IS NOT NULL
                AND longitude IS NOT NULL
            """)
            result = db.execute(query, {"ids": request.competitor_ids})
        else:
            # Fetch nearest competitors using Haversine formula
            # LEAST/GREATEST clamps the acos input to [-1, 1] to prevent floating-point errors
            # This can happen when two points are at nearly identical locations
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
            # Limit competitors for this attempt
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
                # Mapbox 422 often means routing issues with specific coords
                # Retry with fewer competitors (halve each time, min 3)
                old_max = current_max
                current_max = max(3, current_max // 2)
                logger.warning(f"Mapbox 422 error, retrying with {current_max} competitors (was {old_max})")
                continue
            # Final attempt or non-422 error
            logger.error(f"Mapbox Matrix API error: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=f"Travel time service error: {e.response.status_code}. Please try again."
            )
        except httpx.RequestError as e:
            # Network or connection error
            logger.error(f"Mapbox Matrix API connection error: {e}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="Unable to connect to travel time service. Please try again."
            )
        except ValueError as e:
            # Invalid parameters or configuration
            logger.error(f"Competitor access validation error: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Competitor access error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Competitor access error: {str(e)}")

    # All retries exhausted
    if last_error:
        raise HTTPException(
            status_code=502,
            detail=f"Travel time service error after {max_retries} attempts. Please try again."
        )


@router.get("/matrix/cache-stats/")
async def get_matrix_cache_statistics():
    """
    Get Matrix API cache statistics.

    Shows cache utilization to monitor API cost savings.
    """
    return get_cache_stats()


@router.post("/matrix/clear-cache/")
async def clear_matrix_cache_endpoint():
    """
    Clear the Matrix API cache.

    Use when you need fresh travel time data (e.g., after major traffic changes).
    """
    clear_matrix_cache()
    return {"status": "success", "message": "Matrix cache cleared"}


# =============================================================================
# Datasets API Endpoints (Saved Analyses)
# =============================================================================

from app.services.mapbox_datasets import (
    SavedAnalysisRequest,
    SavedAnalysisResponse,
    DatasetInfo,
    AnalysisType,
    save_analysis,
    list_saved_analyses,
    get_saved_analysis,
    delete_saved_analysis,
    list_datasets,
    get_dataset,
    get_features,
)


class SaveAnalysisRequestBody(BaseModel):
    """Request body for saving an analysis."""
    name: str
    analysis_type: str  # trade_area, market_gap, coverage, competitor, demographic
    center_latitude: float
    center_longitude: float
    geojson: dict  # GeoJSON FeatureCollection
    config: Optional[dict] = None


@router.post("/datasets/save/", response_model=SavedAnalysisResponse)
async def save_analysis_endpoint(request: SaveAnalysisRequestBody):
    """
    Save an analysis as a Mapbox dataset.

    Creates a persistent dataset that can be loaded later or shared.
    The analysis GeoJSON is stored in Mapbox Datasets API.

    **Analysis Types:**
    - `trade_area` - Trade area with POIs and demographics
    - `market_gap` - Identified market gaps
    - `coverage` - Store coverage analysis
    - `competitor` - Competitor analysis
    - `demographic` - Demographic analysis

    **Returns:**
    - Database ID for local reference
    - Mapbox dataset ID for API access
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    try:
        analysis_type = AnalysisType(request.analysis_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid analysis type: {request.analysis_type}. Valid types: {[t.value for t in AnalysisType]}"
        )

    try:
        result = await save_analysis(
            SavedAnalysisRequest(
                name=request.name,
                analysis_type=analysis_type,
                center_latitude=request.center_latitude,
                center_longitude=request.center_longitude,
                geojson=request.geojson,
                config=request.config or {},
            )
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving analysis: {str(e)}")


@router.get("/datasets/", response_model=list[SavedAnalysisResponse])
async def list_saved_analyses_endpoint():
    """
    List all saved analyses.

    Returns analyses saved to Mapbox Datasets with their metadata.
    """
    try:
        return await list_saved_analyses()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing analyses: {str(e)}")


@router.get("/datasets/{analysis_id}/", response_model=SavedAnalysisResponse)
async def get_saved_analysis_endpoint(analysis_id: int):
    """
    Get a specific saved analysis.

    Returns the analysis metadata including the Mapbox dataset ID.
    """
    result = await get_saved_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return result


@router.get("/datasets/{analysis_id}/features/")
async def get_analysis_features_endpoint(analysis_id: int, limit: int = 100):
    """
    Get the GeoJSON features from a saved analysis.

    Returns the actual GeoJSON FeatureCollection stored in the dataset.
    """
    analysis = await get_saved_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

    try:
        features = await get_features(analysis.dataset_id, limit=limit)
        return features
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching features: {str(e)}")


@router.delete("/datasets/{analysis_id}/")
async def delete_saved_analysis_endpoint(analysis_id: int):
    """
    Delete a saved analysis.

    Removes both the local database record and the Mapbox dataset.
    """
    success = await delete_saved_analysis(analysis_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return {"status": "success", "message": f"Analysis {analysis_id} deleted"}


@router.get("/datasets/mapbox/")
async def list_mapbox_datasets_endpoint():
    """
    List all Mapbox datasets for the authenticated user.

    Returns raw dataset information from Mapbox API.
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mapbox access token not configured"
        )

    try:
        datasets = await list_datasets()
        return [d.model_dump() for d in datasets]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing Mapbox datasets: {str(e)}")


# =============================================================================
# Isochrone API Endpoints (Drive-Time Polygons)
# =============================================================================

from app.services.mapbox_isochrone import (
    IsochroneRequest as IsochroneServiceRequest,
    IsochroneResponse,
    IsochroneProfile,
    fetch_isochrone,
    fetch_multi_contour_isochrone,
    DEFAULT_ISOCHRONE_COLORS,
)


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

    **Use Cases:**
    - Visualize service area coverage
    - Identify market gaps
    - Analyze competitor reach
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

    **Example Response:**
    Returns a FeatureCollection with multiple polygon features, each representing
    a different travel time contour.
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

    # Use default colors if not provided
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


# =============================================================================
# Demographic Boundaries API (Census Tracts for Choropleth)
# =============================================================================

# State FIPS codes for target markets
STATE_FIPS = {
    "IA": "19",
    "NE": "31",
    "NV": "32",
    "ID": "16",
}

# Census TIGER boundary service URLs (free)
TIGER_COUNTIES_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/86/query"
TIGER_PLACES_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/24/query"
TIGER_ZCTAS_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/2/query"

# ArcGIS Living Atlas - ACS 2022 demographic data URLs
# Layer 0 = State, Layer 1 = County, Layer 2 = Tract
ACS_POPULATION_BASE = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Total_Population_Boundaries/FeatureServer"
ACS_INCOME_BASE = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Median_Income_by_Race_and_Age_Selp_Emp_Boundaries/FeatureServer"

# Layer indices for different geographies
ACS_LAYERS = {
    "county": 1,
    "tract": 2,
}

# Legacy URLs for backwards compatibility
ACS_POPULATION_URL = f"{ACS_POPULATION_BASE}/2/query"  # Tract level
ACS_INCOME_URL = f"{ACS_INCOME_BASE}/2/query"  # Tract level

# Legacy URL (2020 Census - less detailed)
ARCGIS_CENSUS_TRACTS_URL = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Census_Tracts/FeatureServer/0/query"


@router.get("/demographic-boundaries/")
async def get_demographic_boundaries(
    state: str = Query(..., description="State abbreviation (IA, NE, NV, ID)"),
    metric: str = Query("population", description="Metric to include: population, income, density"),
    geography: str = Query("tract", description="Geography level: tract, county"),
):
    """
    Fetch boundaries with demographic data for choropleth visualization.

    Uses ACS 2022 data from ArcGIS Living Atlas for accurate Population and Income.

    **Parameters:**
    - `state`: State abbreviation (IA, NE, NV, ID)
    - `metric`: Demographic metric (population, income, density)
    - `geography`: Geographic level (tract for Census Tracts, county for Counties)

    **Supported Metrics:**
    - `population`: Total population (ACS 2022)
    - `income`: Median household income (ACS 2022)
    - `density`: Population density (pop/sq mile)

    **Returns:**
    GeoJSON FeatureCollection with properties including:
    - NAME: Boundary name
    - GEOID: Census GEOID
    - TOTAL_POPULATION: Total population (ACS 2022)
    - MEDIAN_INCOME: Median household income (ACS 2022)
    - POP_DENSITY: Population per square mile (calculated)
    - metric_value: The selected metric value for choropleth coloring
    """
    state_upper = state.upper()
    if state_upper not in STATE_FIPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {state}. Supported states: {', '.join(STATE_FIPS.keys())}"
        )

    geography_lower = geography.lower()
    if geography_lower not in ACS_LAYERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid geography: {geography}. Supported: tract, county"
        )

    fips_code = STATE_FIPS[state_upper]
    layer_index = ACS_LAYERS[geography_lower]

    # Choose ArcGIS service based on metric
    # Income uses a different service with B19049_001E (Median Household Income)
    if metric == "income":
        url = f"{ACS_INCOME_BASE}/{layer_index}/query"
        # ACS Income service fields: NAME, GEOID, B19049_001E (median HH income), Shape__Area
        out_fields = "NAME,GEOID,B19049_001E,Shape__Area"
    else:
        url = f"{ACS_POPULATION_BASE}/{layer_index}/query"
        # ACS Population service fields: NAME, GEOID, B01001_001E (total pop), Shape__Area
        # Note: Both tract and county layers use Shape__Area (double underscore)
        out_fields = "NAME,GEOID,B01001_001E,Shape__Area"

    # Build query parameters - filter by state FIPS (first 2 chars of GEOID)
    params = {
        "where": f"GEOID LIKE '{fips_code}%'",
        "outFields": out_fields,
        "f": "geojson",
        "returnGeometry": "true",
        "outSR": "4326",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            geojson = response.json()

            # Process features to add calculated metrics
            if "features" in geojson:
                for feature in geojson["features"]:
                    props = feature.get("properties", {})

                    # Get raw values from ACS data
                    # B01001_001E = Total Population, B19049_001E = Median Household Income
                    pop = props.get("B01001_001E") or 0
                    income = props.get("B19049_001E") or 0
                    # Both services use Shape__Area (double underscore)
                    shape_area = props.get("Shape__Area") or 0  # in square meters

                    # Calculate density (pop per sq mile)
                    # 1 sq mile = 2,589,988 sq meters
                    land_area_sqmi = shape_area / 2589988 if shape_area > 0 else 0
                    density = pop / land_area_sqmi if land_area_sqmi > 0 else 0

                    # Add standardized fields
                    props["TOTAL_POPULATION"] = pop
                    props["MEDIAN_INCOME"] = income
                    props["POP_DENSITY"] = round(density, 2)
                    props["LAND_AREA_SQMI"] = round(land_area_sqmi, 2)

                    # Add the selected metric as a standardized field for choropleth
                    if metric == "population":
                        props["metric_value"] = pop
                    elif metric == "density":
                        props["metric_value"] = round(density, 2)
                    elif metric == "income":
                        props["metric_value"] = income

            return geojson

        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"ArcGIS API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to ArcGIS API: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching demographic boundaries: {str(e)}"
            )


# =============================================================================
# Census TIGER Boundary Endpoints (Counties, Cities, ZIP Codes)
# =============================================================================

@router.get("/boundaries/counties/")
async def get_county_boundaries(
    state: str = Query(..., description="State abbreviation (IA, NE, NV, ID)"),
):
    """
    Fetch county boundaries for a state from Census TIGER.

    Returns GeoJSON FeatureCollection with county polygons.
    """
    state_upper = state.upper()
    if state_upper not in STATE_FIPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {state}. Supported states: {', '.join(STATE_FIPS.keys())}"
        )

    fips_code = STATE_FIPS[state_upper]

    params = {
        "where": f"STATE = '{fips_code}'",
        "outFields": "NAME,BASENAME,GEOID,STATE,COUNTY,AREALAND",
        "f": "geojson",
        "returnGeometry": "true",
        "outSR": "4326",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(TIGER_COUNTIES_URL, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Census TIGER API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Census TIGER API: {str(e)}"
            )


@router.get("/boundaries/cities/")
async def get_city_boundaries(
    state: str = Query(..., description="State abbreviation (IA, NE, NV, ID)"),
):
    """
    Fetch city/place boundaries for a state from Census TIGER.

    Returns GeoJSON FeatureCollection with city/place polygons.
    """
    state_upper = state.upper()
    if state_upper not in STATE_FIPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {state}. Supported states: {', '.join(STATE_FIPS.keys())}"
        )

    fips_code = STATE_FIPS[state_upper]

    params = {
        "where": f"STATE = '{fips_code}'",
        "outFields": "NAME,BASENAME,GEOID,STATE,AREALAND,FUNCSTAT",
        "f": "geojson",
        "returnGeometry": "true",
        "outSR": "4326",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(TIGER_PLACES_URL, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Census TIGER API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Census TIGER API: {str(e)}"
            )


@router.get("/boundaries/zipcodes/")
async def get_zipcode_boundaries(
    state: str = Query(..., description="State abbreviation (IA, NE, NV, ID)"),
):
    """
    Fetch ZIP Code (ZCTA) boundaries for a state from Census TIGER.

    Returns GeoJSON FeatureCollection with ZCTA polygons.
    Note: ZCTAs (ZIP Code Tabulation Areas) approximate ZIP codes for census purposes.
    """
    state_upper = state.upper()
    if state_upper not in STATE_FIPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {state}. Supported states: {', '.join(STATE_FIPS.keys())}"
        )

    fips_code = STATE_FIPS[state_upper]

    # ZCTAs don't have a STATE field, so we need to filter by GEOID prefix
    # ZCTA GEOIDs start with the first 3 digits of ZIP codes
    # We'll need to get all and filter, or use a bounding box
    # For now, we use the INTPTLAT/INTPTLON to filter approximately

    # Alternative: Query by state bounding box
    state_bounds = {
        "IA": {"minX": -96.7, "minY": 40.3, "maxX": -90.1, "maxY": 43.6},
        "NE": {"minX": -104.1, "minY": 39.9, "maxX": -95.3, "maxY": 43.1},
        "NV": {"minX": -120.1, "minY": 35.0, "maxX": -114.0, "maxY": 42.1},
        "ID": {"minX": -117.3, "minY": 41.9, "maxX": -111.0, "maxY": 49.1},
    }

    bounds = state_bounds[state_upper]

    params = {
        "where": "1=1",
        "geometry": f"{bounds['minX']},{bounds['minY']},{bounds['maxX']},{bounds['maxY']}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "NAME,BASENAME,GEOID,AREALAND,ZCTA5CE20",
        "f": "geojson",
        "returnGeometry": "true",
        "outSR": "4326",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            response = await client.get(TIGER_ZCTAS_URL, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Census TIGER API error: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Census TIGER API: {str(e)}"
            )


# =============================================================================
# Store Coordinate Validation Endpoint
# =============================================================================

# Continental US bounding box
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

    Checks for:
    - Null coordinates
    - Zero coordinates (0, 0)
    - Coordinates outside continental US bounds

    Returns a summary of issues found.
    """
    db = next(get_db())
    try:
        # Build query
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

        # Validate each store
        null_coords = []
        zero_coords = []
        out_of_bounds = []

        for store in stores:
            store_id, store_brand, street, city, state, lat, lng = store

            # Check for null
            if lat is None or lng is None:
                null_coords.append({
                    "id": store_id,
                    "brand": store_brand,
                    "address": f"{street}, {city}, {state}" if street else f"{city}, {state}",
                    "issue": "NULL_COORDS",
                })
                continue

            # Check for zero
            if lat == 0 and lng == 0:
                zero_coords.append({
                    "id": store_id,
                    "brand": store_brand,
                    "address": f"{street}, {city}, {state}" if street else f"{city}, {state}",
                    "issue": "ZERO_COORDS",
                })
                continue

            # Check bounds
            if not (US_BOUNDS["min_lat"] <= lat <= US_BOUNDS["max_lat"]) or \
               not (US_BOUNDS["min_lng"] <= lng <= US_BOUNDS["max_lng"]):
                out_of_bounds.append({
                    "id": store_id,
                    "brand": store_brand,
                    "lat": lat,
                    "lng": lng,
                    "issue": "OUT_OF_BOUNDS",
                })

        # Combine all issues
        all_issues = null_coords + zero_coords + out_of_bounds

        return ValidationResult(
            total_checked=len(stores),
            null_coords=len(null_coords),
            zero_coords=len(zero_coords),
            out_of_bounds=len(out_of_bounds),
            issues=all_issues[:50],  # Limit issues returned
        )

    except Exception as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")
    finally:
        db.close()
