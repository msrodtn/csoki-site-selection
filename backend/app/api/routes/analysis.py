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
from app.services.property_search import search_properties, PropertySearchResult, MapBounds, check_api_keys as check_property_api_keys
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
