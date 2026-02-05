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

    Fetches nearby points of interest (POIs) within the specified radius
    and categorizes them into: anchors, quick_service, restaurants, retail.

    Uses Mapbox Search Box API (primary) or Google Places API (fallback).

    - **latitude**: Center point latitude
    - **longitude**: Center point longitude
    - **radius_miles**: Search radius in miles (default: 1.0)
    """
    # Convert miles to meters (1 mile = 1609.34 meters)
    radius_meters = int(request.radius_miles * 1609.34)

    # Cap at 50km
    if radius_meters > 50000:
        radius_meters = 50000

    # Prefer Mapbox if configured (8x cheaper: ~$0.004 vs $0.032 per analysis)
    if settings.MAPBOX_ACCESS_TOKEN:
        try:
            logger.info(f"Attempting Mapbox POI search for ({request.latitude}, {request.longitude})")
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
            
            logger.info(f"✅ Mapbox POI search succeeded: {len(pois)} POIs found")
            return result
            
        except ValueError as e:
            # Token not configured or invalid
            logger.warning(f"Mapbox POI search failed (configuration issue): {e}")
        except Exception as e:
            # API error, network issue, or other failure
            logger.warning(f"Mapbox POI search failed, falling back to Google Places: {e}", exc_info=True)

    # Fallback to Google Places (more expensive but reliable)
    if not settings.GOOGLE_PLACES_API_KEY:
        logger.error("No POI API configured: Both Mapbox and Google Places unavailable")
        raise HTTPException(
            status_code=503,
            detail="No POI search API configured. Please set MAPBOX_ACCESS_TOKEN or GOOGLE_PLACES_API_KEY in Railway environment variables."
        )
    
    logger.info(f"Using Google Places API fallback for ({request.latitude}, {request.longitude})")
    
    try:
        result = await fetch_nearby_pois(
            latitude=request.latitude,
            longitude=request.longitude,
            radius_meters=radius_meters,
        )
        logger.info(f"✅ Google Places search succeeded: {len(result.pois)} POIs found")
        return result
    except Exception as e:
        logger.error(f"Google Places API also failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"POI search failed: {str(e)}"
        )

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
            # Fetch nearest competitors using simple distance calculation
            # This approach works even without PostGIS spatial index
            query = text("""
                SELECT id, brand, street, city, state, postal_code, latitude, longitude,
                       (
                           3959 * acos(
                               cos(radians(:lat)) * cos(radians(latitude)) *
                               cos(radians(longitude) - radians(:lng)) +
                               sin(radians(:lat)) * sin(radians(latitude))
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
        db.close()
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

    try:
        access_result = await analyze_competitor_access(
            site_location=(request.site_longitude, request.site_latitude),
            competitor_locations=competitors,
            profile=profile,
            max_competitors=request.max_competitors,
        )
        return access_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Competitor access error: {str(e)}")


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
