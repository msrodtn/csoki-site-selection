"""
ArcGIS GeoEnrichment service for demographic data.

Uses the ArcGIS GeoEnrichment API to fetch population, income, employment,
and consumer spending data for a given location at multiple radii.
"""
import httpx
from typing import Optional
from pydantic import BaseModel

from app.core.config import settings


class DemographicMetrics(BaseModel):
    """Demographic metrics for a single radius."""
    radius_miles: float

    # Population
    total_population: Optional[int] = None
    total_households: Optional[int] = None
    population_density: Optional[float] = None  # per sq mile
    median_age: Optional[float] = None

    # Income
    median_household_income: Optional[int] = None
    average_household_income: Optional[int] = None
    per_capita_income: Optional[int] = None

    # Employment
    total_businesses: Optional[int] = None
    total_employees: Optional[int] = None

    # Consumer Spending (annual, total for area)
    spending_food_away: Optional[int] = None  # Food away from home
    spending_apparel: Optional[int] = None  # Apparel & services
    spending_entertainment: Optional[int] = None  # Entertainment/recreation
    spending_retail_total: Optional[int] = None  # Total retail spending


class DemographicsResponse(BaseModel):
    """Demographics response with data at multiple radii."""
    latitude: float
    longitude: float
    radii: list[DemographicMetrics]
    data_vintage: str = "2025"  # Esri data vintage


# ArcGIS GeoEnrichment analysis variables
# Using Esri's standard US data collections
ANALYSIS_VARIABLES = [
    # Population
    "KeyGlobalFacts.TOTPOP",        # Total Population
    "KeyGlobalFacts.TOTHH",         # Total Households
    "KeyUSFacts.POPDENS_CY",        # Population Density
    "KeyUSFacts.MEDAGE_CY",         # Median Age

    # Income
    "KeyUSFacts.MEDHINC_CY",        # Median Household Income
    "KeyUSFacts.AVGHINC_CY",        # Average Household Income
    "KeyUSFacts.PCI_CY",            # Per Capita Income

    # Business/Employment
    "KeyUSFacts.TOTBUS_CY",         # Total Businesses
    "KeyUSFacts.TOTEMP_CY",         # Total Employees

    # Consumer Spending (from Esri Consumer Spending data)
    "spending.X1001_X",             # Food Away from Home
    "spending.X2001_X",             # Apparel & Services
    "spending.X4001_X",             # Entertainment/Recreation
    "spending.X5001_X",             # Retail Goods Total
]


async def fetch_demographics(
    latitude: float,
    longitude: float,
    radii_miles: list[float] = [1, 3, 5]
) -> DemographicsResponse:
    """
    Fetch demographic data from ArcGIS GeoEnrichment API.

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        radii_miles: List of radii to analyze (default: 1, 3, 5 miles)

    Returns:
        DemographicsResponse with data for each radius
    """
    api_key = settings.ARCGIS_API_KEY
    if not api_key:
        raise ValueError("ArcGIS API key not configured. Set ARCGIS_API_KEY environment variable.")

    # Build study areas for multiple radii
    study_areas = [{
        "geometry": {
            "x": longitude,
            "y": latitude
        },
        "areaType": "RingBuffer",
        "bufferUnits": "esriMiles",
        "bufferRadii": radii_miles
    }]

    # GeoEnrichment API endpoint
    url = "https://geoenrich.arcgis.com/arcgis/rest/services/World/geoenrichmentserver/GeoEnrichment/enrich"

    params = {
        "studyAreas": str(study_areas).replace("'", '"'),
        "analysisVariables": str(ANALYSIS_VARIABLES).replace("'", '"'),
        "returnGeometry": "false",
        "f": "json",
        "token": api_key
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=params, timeout=30)
        response.raise_for_status()
        data = response.json()

    # Check for errors
    if "error" in data:
        error_msg = data["error"].get("message", "Unknown ArcGIS error")
        raise ValueError(f"ArcGIS API error: {error_msg}")

    # Parse results
    results = []

    if "results" in data and data["results"]:
        feature_set = data["results"][0].get("value", {}).get("FeatureSet", [])

        for i, fs in enumerate(feature_set):
            if "features" in fs and fs["features"]:
                attrs = fs["features"][0].get("attributes", {})

                # Map to our model
                metrics = DemographicMetrics(
                    radius_miles=radii_miles[i] if i < len(radii_miles) else radii_miles[-1],

                    # Population
                    total_population=safe_int(attrs.get("KeyGlobalFacts.TOTPOP")),
                    total_households=safe_int(attrs.get("KeyGlobalFacts.TOTHH")),
                    population_density=safe_float(attrs.get("KeyUSFacts.POPDENS_CY")),
                    median_age=safe_float(attrs.get("KeyUSFacts.MEDAGE_CY")),

                    # Income
                    median_household_income=safe_int(attrs.get("KeyUSFacts.MEDHINC_CY")),
                    average_household_income=safe_int(attrs.get("KeyUSFacts.AVGHINC_CY")),
                    per_capita_income=safe_int(attrs.get("KeyUSFacts.PCI_CY")),

                    # Employment
                    total_businesses=safe_int(attrs.get("KeyUSFacts.TOTBUS_CY")),
                    total_employees=safe_int(attrs.get("KeyUSFacts.TOTEMP_CY")),

                    # Consumer Spending
                    spending_food_away=safe_int(attrs.get("spending.X1001_X")),
                    spending_apparel=safe_int(attrs.get("spending.X2001_X")),
                    spending_entertainment=safe_int(attrs.get("spending.X4001_X")),
                    spending_retail_total=safe_int(attrs.get("spending.X5001_X")),
                )
                results.append(metrics)

    # If no results, return empty metrics for each radius
    if not results:
        results = [DemographicMetrics(radius_miles=r) for r in radii_miles]

    return DemographicsResponse(
        latitude=latitude,
        longitude=longitude,
        radii=results
    )


def safe_int(value) -> Optional[int]:
    """Safely convert value to int."""
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def safe_float(value) -> Optional[float]:
    """Safely convert value to float."""
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (ValueError, TypeError):
        return None
