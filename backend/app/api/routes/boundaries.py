"""
Boundary & demographic choropleth API endpoints.

Includes:
- ACS demographic boundaries (population, income, density choropleth)
- Census TIGER boundaries (counties, cities, ZIP codes)
"""
import httpx
import logging
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


# State FIPS codes for all 50 states + DC
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56",
}

# Census TIGER boundary service URLs (free)
TIGER_COUNTIES_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/86/query"
TIGER_PLACES_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/24/query"
TIGER_ZCTAS_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2021/MapServer/2/query"

# ArcGIS Living Atlas - ACS 2022 demographic data URLs
ACS_POPULATION_BASE = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Total_Population_Boundaries/FeatureServer"
ACS_INCOME_BASE = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Median_Income_by_Race_and_Age_Selp_Emp_Boundaries/FeatureServer"

ACS_LAYERS = {
    "county": 1,
    "tract": 2,
}

# State bounding boxes for ZCTA queries (ZCTAs don't have a STATE field)
STATE_BOUNDS = {
    "AL": {"minX": -88.5, "minY": 30.1, "maxX": -84.9, "maxY": 35.0},
    "AK": {"minX": -179.2, "minY": 51.2, "maxX": -129.0, "maxY": 71.4},
    "AZ": {"minX": -114.8, "minY": 31.3, "maxX": -109.0, "maxY": 37.0},
    "AR": {"minX": -94.6, "minY": 33.0, "maxX": -89.6, "maxY": 36.5},
    "CA": {"minX": -124.5, "minY": 32.5, "maxX": -114.1, "maxY": 42.0},
    "CO": {"minX": -109.1, "minY": 36.9, "maxX": -102.0, "maxY": 41.0},
    "CT": {"minX": -73.7, "minY": 41.0, "maxX": -71.8, "maxY": 42.1},
    "DE": {"minX": -75.8, "minY": 38.4, "maxX": -75.0, "maxY": 39.8},
    "DC": {"minX": -77.1, "minY": 38.8, "maxX": -76.9, "maxY": 39.0},
    "FL": {"minX": -87.6, "minY": 24.4, "maxX": -80.0, "maxY": 31.0},
    "GA": {"minX": -85.6, "minY": 30.4, "maxX": -80.8, "maxY": 35.0},
    "HI": {"minX": -160.3, "minY": 18.9, "maxX": -154.8, "maxY": 22.3},
    "ID": {"minX": -117.3, "minY": 41.9, "maxX": -111.0, "maxY": 49.1},
    "IL": {"minX": -91.5, "minY": 36.9, "maxX": -87.0, "maxY": 42.5},
    "IN": {"minX": -88.1, "minY": 37.8, "maxX": -84.8, "maxY": 41.8},
    "IA": {"minX": -96.7, "minY": 40.3, "maxX": -90.1, "maxY": 43.6},
    "KS": {"minX": -102.1, "minY": 36.9, "maxX": -94.6, "maxY": 40.0},
    "KY": {"minX": -89.6, "minY": 36.5, "maxX": -81.9, "maxY": 39.2},
    "LA": {"minX": -94.1, "minY": 28.9, "maxX": -88.8, "maxY": 33.0},
    "ME": {"minX": -71.1, "minY": 43.0, "maxX": -66.9, "maxY": 47.5},
    "MD": {"minX": -79.5, "minY": 37.9, "maxX": -75.0, "maxY": 39.7},
    "MA": {"minX": -73.5, "minY": 41.2, "maxX": -69.9, "maxY": 42.9},
    "MI": {"minX": -90.4, "minY": 41.7, "maxX": -82.1, "maxY": 48.3},
    "MN": {"minX": -97.3, "minY": 43.5, "maxX": -89.5, "maxY": 49.4},
    "MS": {"minX": -91.7, "minY": 30.1, "maxX": -88.1, "maxY": 35.0},
    "MO": {"minX": -95.8, "minY": 36.0, "maxX": -89.1, "maxY": 40.6},
    "MT": {"minX": -116.1, "minY": 44.4, "maxX": -104.0, "maxY": 49.0},
    "NE": {"minX": -104.1, "minY": 39.9, "maxX": -95.3, "maxY": 43.1},
    "NV": {"minX": -120.1, "minY": 35.0, "maxX": -114.0, "maxY": 42.1},
    "NH": {"minX": -72.6, "minY": 42.7, "maxX": -70.7, "maxY": 45.3},
    "NJ": {"minX": -75.6, "minY": 38.9, "maxX": -73.9, "maxY": 41.4},
    "NM": {"minX": -109.1, "minY": 31.3, "maxX": -103.0, "maxY": 37.0},
    "NY": {"minX": -79.8, "minY": 40.5, "maxX": -71.9, "maxY": 45.0},
    "NC": {"minX": -84.3, "minY": 33.8, "maxX": -75.5, "maxY": 36.6},
    "ND": {"minX": -104.1, "minY": 45.9, "maxX": -96.6, "maxY": 49.0},
    "OH": {"minX": -84.8, "minY": 38.4, "maxX": -80.5, "maxY": 42.0},
    "OK": {"minX": -103.0, "minY": 33.6, "maxX": -94.4, "maxY": 37.0},
    "OR": {"minX": -124.6, "minY": 41.9, "maxX": -116.5, "maxY": 46.3},
    "PA": {"minX": -80.5, "minY": 39.7, "maxX": -74.7, "maxY": 42.3},
    "RI": {"minX": -71.9, "minY": 41.1, "maxX": -71.1, "maxY": 42.0},
    "SC": {"minX": -83.4, "minY": 32.0, "maxX": -78.5, "maxY": 35.2},
    "SD": {"minX": -104.1, "minY": 42.5, "maxX": -96.4, "maxY": 46.0},
    "TN": {"minX": -90.3, "minY": 35.0, "maxX": -81.6, "maxY": 36.7},
    "TX": {"minX": -106.7, "minY": 25.8, "maxX": -93.5, "maxY": 36.5},
    "UT": {"minX": -114.1, "minY": 37.0, "maxX": -109.0, "maxY": 42.0},
    "VT": {"minX": -73.4, "minY": 42.7, "maxX": -71.5, "maxY": 45.0},
    "VA": {"minX": -83.7, "minY": 36.5, "maxX": -75.2, "maxY": 39.5},
    "WA": {"minX": -124.8, "minY": 45.5, "maxX": -116.9, "maxY": 49.0},
    "WV": {"minX": -82.6, "minY": 37.2, "maxX": -77.7, "maxY": 40.6},
    "WI": {"minX": -92.9, "minY": 42.5, "maxX": -86.2, "maxY": 47.1},
    "WY": {"minX": -111.1, "minY": 40.9, "maxX": -104.1, "maxY": 45.0},
}


# =============================================================================
# Demographic Boundaries (ACS Choropleth)
# =============================================================================

@router.get("/demographic-boundaries/")
async def get_demographic_boundaries(
    state: str = Query(..., description="Two-letter state abbreviation (e.g., IA, NE, CA, TX)"),
    metric: str = Query("population", description="Metric to include: population, income, density"),
    geography: str = Query("tract", description="Geography level: tract, county"),
):
    """
    Fetch boundaries with demographic data for choropleth visualization.

    Uses ACS 2022 data from ArcGIS Living Atlas.

    **Supported Metrics:** population, income, density
    **Geography Levels:** tract, county

    **Returns:** GeoJSON FeatureCollection with TOTAL_POPULATION, MEDIAN_INCOME, POP_DENSITY
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

    if metric == "income":
        url = f"{ACS_INCOME_BASE}/{layer_index}/query"
        out_fields = "NAME,GEOID,B19049_001E,Shape__Area"
    else:
        url = f"{ACS_POPULATION_BASE}/{layer_index}/query"
        out_fields = "NAME,GEOID,B01001_001E,Shape__Area"

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

            if "features" in geojson:
                for feature in geojson["features"]:
                    props = feature.get("properties", {})

                    pop = props.get("B01001_001E") or 0
                    income = props.get("B19049_001E") or 0
                    shape_area = props.get("Shape__Area") or 0

                    land_area_sqmi = shape_area / 2589988 if shape_area > 0 else 0
                    density = pop / land_area_sqmi if land_area_sqmi > 0 else 0

                    props["TOTAL_POPULATION"] = pop
                    props["MEDIAN_INCOME"] = income
                    props["POP_DENSITY"] = round(density, 2)
                    props["LAND_AREA_SQMI"] = round(land_area_sqmi, 2)

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
    state: str = Query(..., description="Two-letter state abbreviation"),
):
    """Fetch county boundaries for a state from Census TIGER."""
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
    state: str = Query(..., description="Two-letter state abbreviation"),
):
    """Fetch city/place boundaries for a state from Census TIGER."""
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
    state: str = Query(..., description="Two-letter state abbreviation"),
):
    """
    Fetch ZIP Code (ZCTA) boundaries for a state from Census TIGER.

    Note: ZCTAs approximate ZIP codes for census purposes.
    Uses state bounding box since ZCTAs don't have a STATE field.
    """
    state_upper = state.upper()
    if state_upper not in STATE_FIPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {state}. Supported states: {', '.join(STATE_FIPS.keys())}"
        )

    bounds = STATE_BOUNDS[state_upper]

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
