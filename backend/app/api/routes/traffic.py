"""
Traffic Count Data API

Serves state DOT traffic count data (AADT) from various sources.
Proxies ArcGIS REST services and caches responses for performance.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import httpx
from datetime import datetime, timedelta

router = APIRouter()

# State DOT service URLs
STATE_SERVICES = {
    "IA": {
        "name": "Iowa",
        "url": "https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/Traffic_Data_view/FeatureServer/10",
        "fields": "AADT,ROUTE_NAME,STATESIGNED,COUNTYSIGNED,AADT_YEAR",
    },
    # Future states:
    # "NE": {"name": "Nebraska", "url": "...", "fields": "..."},
    # "NV": {"name": "Nevada", "url": "...", "fields": "..."},
}

# Simple in-memory cache (will expire on restart)
# TODO: Move to Redis for production
_cache: Dict[str, tuple[Any, datetime]] = {}
CACHE_TTL = timedelta(hours=24)


@router.get("/states")
async def list_available_states():
    """
    Get list of states with traffic data available.
    
    Returns:
        List of state codes and names
    """
    return {
        "states": [
            {"code": code, "name": config["name"]}
            for code, config in STATE_SERVICES.items()
        ]
    }


@router.get("/{state_code}")
async def get_traffic_data(state_code: str):
    """
    Get traffic count data for a specific state.
    
    Args:
        state_code: Two-letter state code (e.g., "IA", "NE")
    
    Returns:
        GeoJSON FeatureCollection with traffic count data
    
    Raises:
        HTTPException: If state not found or data fetch fails
    """
    state_code = state_code.upper()
    
    # Validate state
    if state_code not in STATE_SERVICES:
        raise HTTPException(
            status_code=404,
            detail=f"Traffic data not available for state: {state_code}. Available: {list(STATE_SERVICES.keys())}"
        )
    
    # Check cache
    cache_key = f"traffic_{state_code}"
    if cache_key in _cache:
        data, cached_at = _cache[cache_key]
        if datetime.now() - cached_at < CACHE_TTL:
            return data
    
    # Fetch from ArcGIS
    service = STATE_SERVICES[state_code]
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{service['url']}/query",
                params={
                    "where": "1=1",
                    "outFields": service["fields"],
                    "returnGeometry": "true",
                    "f": "geojson",
                    "resultRecordCount": 2000,
                }
            )
            response.raise_for_status()
            geojson = response.json()
            
            # Add metadata
            result = {
                **geojson,
                "metadata": {
                    "state": state_code,
                    "state_name": service["name"],
                    "fetched_at": datetime.now().isoformat(),
                    "feature_count": len(geojson.get("features", [])),
                }
            }
            
            # Cache result
            _cache[cache_key] = (result, datetime.now())
            
            return result
            
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch traffic data from state DOT: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing traffic data: {str(e)}"
        )


@router.delete("/cache/{state_code}")
async def clear_cache(state_code: str):
    """
    Clear cached traffic data for a state (admin/debug endpoint).
    
    Args:
        state_code: Two-letter state code
    
    Returns:
        Success message
    """
    state_code = state_code.upper()
    cache_key = f"traffic_{state_code}"
    
    if cache_key in _cache:
        del _cache[cache_key]
        return {"message": f"Cache cleared for {state_code}"}
    
    return {"message": f"No cache found for {state_code}"}
