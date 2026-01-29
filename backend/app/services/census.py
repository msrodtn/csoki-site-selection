"""
Census Bureau API service for supplemental demographic data.

Uses Census Bureau APIs to fetch data that ArcGIS doesn't provide:
- Median Age (from ACS 5-Year Estimates)
- Total Businesses (from County Business Patterns)
- Total Employees (from County Business Patterns)

The FCC API is used to convert lat/lng coordinates to census geography (FIPS codes).
"""
import httpx
from typing import Optional
from pydantic import BaseModel

from app.core.config import settings


class CensusGeography(BaseModel):
    """Census geography identifiers from FCC geocoder."""
    state_fips: str
    county_fips: str
    tract_fips: str
    block_fips: Optional[str] = None


class CensusData(BaseModel):
    """Census data for a location."""
    # From ACS 5-Year Estimates
    median_age: Optional[float] = None

    # From County Business Patterns (county-level)
    total_businesses: Optional[int] = None
    total_employees: Optional[int] = None

    # Data source info
    acs_year: str = "2022"  # Most recent ACS 5-year
    cbp_year: str = "2021"  # Most recent CBP


async def get_census_geography(latitude: float, longitude: float) -> Optional[CensusGeography]:
    """
    Convert lat/lng to Census geography (FIPS codes) using FCC API.

    The FCC Area API is free and doesn't require authentication.
    """
    url = "https://geo.fcc.gov/api/census/block/find"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "format": "json",
        "showall": "false"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "OK" and data.get("Block"):
                fips = data["Block"]["FIPS"]
                # FIPS format: SSCCCTTTTTTBBBB (state, county, tract, block)
                return CensusGeography(
                    state_fips=fips[0:2],
                    county_fips=fips[2:5],
                    tract_fips=fips[5:11],
                    block_fips=fips[11:15] if len(fips) > 11 else None
                )
            return None
        except Exception as e:
            print(f"FCC geocoding error: {e}")
            return None


async def fetch_acs_median_age(
    state_fips: str,
    county_fips: str,
    tract_fips: str,
    api_key: str
) -> Optional[float]:
    """
    Fetch median age from ACS 5-Year Estimates at tract level.

    Variable: B01002_001E = Median Age
    """
    # ACS 5-Year Estimates API
    url = "https://api.census.gov/data/2022/acs/acs5"
    params = {
        "get": "B01002_001E",  # Median Age
        "for": f"tract:{tract_fips}",
        "in": f"state:{state_fips} county:{county_fips}",
        "key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Response format: [["B01002_001E", "state", "county", "tract"], ["35.2", "19", "153", "001700"]]
            if len(data) > 1 and data[1][0]:
                return float(data[1][0])
            return None
        except Exception as e:
            print(f"ACS API error: {e}")
            return None


async def fetch_cbp_business_data(
    state_fips: str,
    county_fips: str,
    api_key: str
) -> tuple[Optional[int], Optional[int]]:
    """
    Fetch business and employee counts from County Business Patterns.

    CBP provides data at county level (not tract level).
    Variables:
    - ESTAB = Number of establishments
    - EMP = Number of employees
    """
    # County Business Patterns API (most recent year)
    url = "https://api.census.gov/data/2021/cbp"
    params = {
        "get": "ESTAB,EMP",
        "for": f"county:{county_fips}",
        "in": f"state:{state_fips}",
        "NAICS2017": "00",  # All industries
        "key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Response format: [["ESTAB", "EMP", "state", "county", "NAICS2017"], ["1234", "5678", "19", "153", "00"]]
            if len(data) > 1:
                row = data[1]
                estab = int(row[0]) if row[0] else None
                emp = int(row[1]) if row[1] else None
                return estab, emp
            return None, None
        except Exception as e:
            print(f"CBP API error: {e}")
            return None, None


async def fetch_census_data(latitude: float, longitude: float) -> CensusData:
    """
    Fetch supplemental demographic data from Census Bureau APIs.

    This fetches data that ArcGIS GeoEnrichment doesn't provide:
    - Median Age (tract-level from ACS)
    - Total Businesses (county-level from CBP)
    - Total Employees (county-level from CBP)
    """
    api_key = settings.CENSUS_API_KEY
    if not api_key:
        return CensusData()

    # Step 1: Get census geography from coordinates
    geography = await get_census_geography(latitude, longitude)
    if not geography:
        return CensusData()

    # Step 2: Fetch data in parallel
    import asyncio

    median_age_task = fetch_acs_median_age(
        geography.state_fips,
        geography.county_fips,
        geography.tract_fips,
        api_key
    )

    cbp_task = fetch_cbp_business_data(
        geography.state_fips,
        geography.county_fips,
        api_key
    )

    median_age, (businesses, employees) = await asyncio.gather(
        median_age_task,
        cbp_task
    )

    return CensusData(
        median_age=median_age,
        total_businesses=businesses,
        total_employees=employees
    )
