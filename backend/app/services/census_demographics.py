"""
Census Bureau-based demographics service to replace ArcGIS GeoEnrichment.

Implements area-weighted ring buffer analysis using Census tract-level data:
- Uses Census TIGER tract boundaries for spatial analysis
- Weights demographic values by the percentage of each tract's area within the buffer
- Provides the same API signature as the ArcGIS service for drop-in replacement

Data sources:
- ACS 5-Year Estimates API for demographics
- County Business Patterns API for business/employment data
- Census TIGER tract shapefiles for spatial analysis (loaded into PostGIS)

Note: Consumer spending data is not available from Census Bureau (Esri proprietary).
"""
import asyncio
import httpx
import math
from typing import Optional, List, Dict, Tuple
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.arcgis import DemographicMetrics, DemographicsResponse


class CensusTract(BaseModel):
    """Census tract with geometry and identifiers."""
    geoid: str  # Full tract GEOID (state+county+tract)
    state_fips: str
    county_fips: str 
    tract_fips: str
    area_sqmiles: float
    intersection_ratio: float  # Percentage of tract area within buffer


class CensusDemographicsService:
    """
    Census Bureau demographics service using area-weighted ring buffer analysis.
    
    This service replicates the functionality of ArcGIS GeoEnrichment using
    free Census Bureau APIs and TIGER tract boundaries stored in PostGIS.
    """
    
    def __init__(self):
        self.engine = create_engine(settings.DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
        
        # ACS 5-Year Estimates variables
        self.acs_variables = {
            "B01003_001E": "total_population",
            "B11001_001E": "total_households", 
            "B01002_001E": "median_age",
            "B19013_001E": "median_household_income",
            "B19025_001E": "aggregate_household_income",
            "B19301_001E": "per_capita_income"
        }
        
        # County Business Patterns variables
        self.cbp_variables = {
            "ESTAB": "total_businesses",
            "EMP": "total_employees"
        }

    async def fetch_demographics(
        self,
        latitude: float,
        longitude: float,
        radii_miles: List[float] = [1, 3, 5]
    ) -> DemographicsResponse:
        """
        Fetch demographic data using Census Bureau APIs with area-weighted ring buffer analysis.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude  
            radii_miles: List of radii to analyze (default: 1, 3, 5 miles)
            
        Returns:
            DemographicsResponse matching ArcGIS service format
        """
        results = []
        
        for radius in radii_miles:
            try:
                # Get intersecting tracts with area weights
                tracts = await self._get_intersecting_tracts(latitude, longitude, radius)
                
                if not tracts:
                    # No tracts found, return empty metrics
                    results.append(DemographicMetrics(radius_miles=radius))
                    continue
                
                # Fetch ACS demographic data for all tracts
                acs_data = await self._fetch_acs_data(tracts)
                
                # Fetch CBP business data at county level
                cbp_data = await self._fetch_cbp_data(tracts)
                
                # Calculate area-weighted totals
                metrics = self._calculate_weighted_demographics(
                    radius, tracts, acs_data, cbp_data
                )
                
                results.append(metrics)
                
            except Exception as e:
                print(f"Error fetching demographics for radius {radius}: {e}")
                results.append(DemographicMetrics(radius_miles=radius))
        
        return DemographicsResponse(
            latitude=latitude,
            longitude=longitude,
            radii=results,
            data_vintage="2022",  # ACS 5-Year 2022
            census_supplemented=True  # All data from Census Bureau
        )

    async def _get_intersecting_tracts(
        self, 
        latitude: float, 
        longitude: float, 
        radius_miles: float
    ) -> List[CensusTract]:
        """
        Find Census tracts that intersect with the buffer circle and calculate area weights.
        
        Uses PostGIS spatial functions to:
        1. Create a buffer circle around the point
        2. Find intersecting tracts
        3. Calculate the percentage of each tract's area within the buffer
        """
        # Convert radius from miles to meters for PostGIS
        radius_meters = radius_miles * 1609.34
        
        query = text("""
            WITH buffer AS (
                SELECT ST_Transform(
                    ST_Buffer(
                        ST_Transform(ST_SetSRID(ST_Point(:lng, :lat), 4326), 3857),
                        :radius_m
                    ), 4326
                ) AS geom
            ),
            intersecting AS (
                SELECT 
                    t.geoid,
                    t.statefp AS state_fips,
                    t.countyfp AS county_fips,
                    t.tractce AS tract_fips,
                    t.aland / 2589988.11 AS area_sqmiles,  -- Convert sq meters to sq miles
                    ST_Area(ST_Intersection(t.geom, b.geom)) / ST_Area(t.geom) AS intersection_ratio
                FROM census_tracts t, buffer b
                WHERE ST_Intersects(t.geom, b.geom)
                    AND t.statefp IN ('19', '31', '32', '16')  -- IA, NE, NV, ID
            )
            SELECT * FROM intersecting
            WHERE intersection_ratio > 0.01  -- Only include tracts with >1% overlap
            ORDER BY intersection_ratio DESC;
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {
                'lat': latitude,
                'lng': longitude, 
                'radius_m': radius_meters
            })
            
            tracts = []
            for row in result:
                tracts.append(CensusTract(
                    geoid=row.geoid,
                    state_fips=row.state_fips,
                    county_fips=row.county_fips,
                    tract_fips=row.tract_fips,
                    area_sqmiles=row.area_sqmiles,
                    intersection_ratio=row.intersection_ratio
                ))
            
            return tracts

    async def _fetch_acs_data(self, tracts: List[CensusTract]) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Fetch ACS 5-Year Estimates data for all tracts.
        
        Groups tracts by state+county for efficient API calls.
        """
        # Group tracts by state+county for batch API calls
        state_counties = {}
        for tract in tracts:
            key = f"{tract.state_fips}_{tract.county_fips}"
            if key not in state_counties:
                state_counties[key] = []
            state_counties[key].append(tract.tract_fips)
        
        all_data = {}
        
        for state_county, tract_list in state_counties.items():
            state_fips, county_fips = state_county.split('_')
            
            # Create tract list for API call
            tract_str = ','.join(tract_list)
            
            try:
                data = await self._call_acs_api(state_fips, county_fips, tract_str)
                all_data.update(data)
            except Exception as e:
                print(f"ACS API error for {state_county}: {e}")
        
        return all_data

    async def _call_acs_api(
        self, 
        state_fips: str, 
        county_fips: str, 
        tract_str: str
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """Call ACS 5-Year Estimates API for specified tracts."""
        url = "https://api.census.gov/data/2022/acs/acs5"
        
        variables = ','.join(self.acs_variables.keys())
        
        params = {
            "get": variables,
            "for": f"tract:{tract_str}",
            "in": f"state:{state_fips} county:{county_fips}"
        }
        
        if settings.CENSUS_API_KEY:
            params["key"] = settings.CENSUS_API_KEY
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        
        # Parse response into dict by tract GEOID
        result = {}
        if len(data) > 1:  # First row is headers
            headers = data[0]
            for row in data[1:]:
                # Build tract GEOID
                state = row[headers.index("state")]
                county = row[headers.index("county")]  
                tract = row[headers.index("tract")]
                geoid = f"{state}{county}{tract}"
                
                # Extract variable values
                tract_data = {}
                for i, var_code in enumerate(self.acs_variables.keys()):
                    if var_code in headers:
                        idx = headers.index(var_code)
                        value = row[idx]
                        tract_data[self.acs_variables[var_code]] = (
                            float(value) if value and value != "-" else None
                        )
                
                result[geoid] = tract_data
        
        return result

    async def _fetch_cbp_data(self, tracts: List[CensusTract]) -> Dict[str, Dict[str, Optional[int]]]:
        """
        Fetch County Business Patterns data.
        
        CBP data is only available at county level, so we fetch once per county
        and apply the same values to all tracts in that county.
        """
        # Get unique state+county combinations
        counties = set((t.state_fips, t.county_fips) for t in tracts)
        
        county_data = {}
        
        for state_fips, county_fips in counties:
            try:
                data = await self._call_cbp_api(state_fips, county_fips)
                county_data[f"{state_fips}{county_fips}"] = data
            except Exception as e:
                print(f"CBP API error for {state_fips}_{county_fips}: {e}")
                county_data[f"{state_fips}{county_fips}"] = {}
        
        # Apply county data to all tracts in that county
        result = {}
        for tract in tracts:
            county_key = f"{tract.state_fips}{tract.county_fips}"
            result[tract.geoid] = county_data.get(county_key, {})
        
        return result

    async def _call_cbp_api(
        self, 
        state_fips: str, 
        county_fips: str
    ) -> Dict[str, Optional[int]]:
        """Call County Business Patterns API for a single county."""
        url = "https://api.census.gov/data/2021/cbp"
        
        params = {
            "get": "ESTAB,EMP",
            "for": f"county:{county_fips}",
            "in": f"state:{state_fips}",
            "NAICS2017": "00"  # All industries
        }
        
        if settings.CENSUS_API_KEY:
            params["key"] = settings.CENSUS_API_KEY
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        
        result = {}
        if len(data) > 1:  # First row is headers  
            row = data[1]
            result["total_businesses"] = int(row[0]) if row[0] else None
            result["total_employees"] = int(row[1]) if row[1] else None
        
        return result

    def _calculate_weighted_demographics(
        self,
        radius: float,
        tracts: List[CensusTract],
        acs_data: Dict[str, Dict[str, Optional[float]]],
        cbp_data: Dict[str, Dict[str, Optional[int]]]
    ) -> DemographicMetrics:
        """
        Calculate area-weighted demographic totals for the buffer.
        
        For each metric:
        1. Multiply tract value by intersection ratio (area weight)
        2. Sum across all intersecting tracts
        3. For income metrics, calculate weighted averages using population/households
        """
        # Weighted totals
        total_population = 0
        total_households = 0
        total_businesses = 0
        total_employees = 0
        total_area = 0
        
        # For weighted averages
        median_age_sum = 0
        median_age_population = 0
        
        income_sum = 0
        income_households = 0
        
        aggregate_income_sum = 0
        per_capita_income_sum = 0
        per_capita_population = 0
        
        for tract in tracts:
            weight = tract.intersection_ratio
            weighted_area = tract.area_sqmiles * weight
            total_area += weighted_area
            
            acs = acs_data.get(tract.geoid, {})
            cbp = cbp_data.get(tract.geoid, {})
            
            # Population metrics (direct weighting)
            if acs.get("total_population"):
                pop = acs["total_population"] * weight
                total_population += pop
                
                # Track for median age weighting
                if acs.get("median_age"):
                    median_age_sum += acs["median_age"] * pop
                    median_age_population += pop
            
            if acs.get("total_households"):
                hh = acs["total_households"] * weight
                total_households += hh
                
                # Track for income weighting
                if acs.get("median_household_income"):
                    income_sum += acs["median_household_income"] * hh
                    income_households += hh
            
            # Aggregate income (for average calculation)
            if acs.get("aggregate_household_income"):
                aggregate_income_sum += acs["aggregate_household_income"] * weight
            
            # Per capita income
            if acs.get("per_capita_income") and acs.get("total_population"):
                pop = acs["total_population"] * weight
                per_capita_income_sum += acs["per_capita_income"] * pop
                per_capita_population += pop
            
            # Business data (county-level, so weight by area)
            if cbp.get("total_businesses"):
                total_businesses += cbp["total_businesses"] * weight
            
            if cbp.get("total_employees"):
                total_employees += cbp["total_employees"] * weight
        
        # Calculate final metrics
        population_density = total_population / total_area if total_area > 0 else None
        
        median_age = (
            median_age_sum / median_age_population 
            if median_age_population > 0 else None
        )
        
        median_household_income = (
            income_sum / income_households 
            if income_households > 0 else None
        )
        
        average_household_income = (
            aggregate_income_sum / total_households 
            if total_households > 0 else None
        )
        
        per_capita_income = (
            per_capita_income_sum / per_capita_population 
            if per_capita_population > 0 else None
        )
        
        return DemographicMetrics(
            radius_miles=radius,
            
            # Population  
            total_population=int(total_population) if total_population > 0 else None,
            total_households=int(total_households) if total_households > 0 else None,
            population_density=round(population_density, 1) if population_density else None,
            median_age=round(median_age, 1) if median_age else None,
            
            # Income
            median_household_income=int(median_household_income) if median_household_income else None,
            average_household_income=int(average_household_income) if average_household_income else None,
            per_capita_income=int(per_capita_income) if per_capita_income else None,
            
            # Employment  
            total_businesses=int(total_businesses) if total_businesses > 0 else None,
            total_employees=int(total_employees) if total_employees > 0 else None,
            
            # Consumer spending - Not available from Census Bureau
            # These fields will remain None as Esri spending data is proprietary
            spending_food_away=None,
            spending_apparel=None, 
            spending_entertainment=None,
            spending_retail_total=None,
        )


# Global service instance
_census_service = None

def get_census_demographics_service() -> CensusDemographicsService:
    """Get singleton instance of CensusDemographicsService."""
    global _census_service
    if _census_service is None:
        _census_service = CensusDemographicsService()
    return _census_service


# Main API function matching ArcGIS service signature
async def fetch_demographics(
    latitude: float,
    longitude: float, 
    radii_miles: List[float] = [1, 3, 5]
) -> DemographicsResponse:
    """
    Fetch demographic data using Census Bureau APIs (replacement for ArcGIS GeoEnrichment).
    
    This function provides the same interface as the ArcGIS service but uses
    Census Bureau data sources and area-weighted spatial analysis.
    
    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        radii_miles: List of radii to analyze (default: 1, 3, 5 miles)
        
    Returns:
        DemographicsResponse with Census-based data
        
    Note: Consumer spending fields will be None as this data is not available
          from Census Bureau (Esri proprietary). All other fields are populated
          using area-weighted analysis of Census tract data.
    """
    service = get_census_demographics_service()
    return await service.fetch_demographics(latitude, longitude, radii_miles)