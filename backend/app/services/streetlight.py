"""
Streetlight Advanced Traffic Counts API service.

Provides traffic volume, speed, traveler demographics, and vehicle attributes
for site selection analysis. Uses the SATC (Streetlight Advanced Traffic Counts) API.

API Documentation: https://developer.streetlightdata.com/docs/intro-to-the-advanced-traffic-counts-api
"""
import httpx
from typing import Optional, Literal
from pydantic import BaseModel
from enum import Enum

from app.core.config import settings


# =============================================================================
# Enums and Constants
# =============================================================================

class TravelMode(str, Enum):
    VEHICLE = "vehicle"
    PEDESTRIAN = "pedestrian"


class DataSource(str, Enum):
    LBS_PLUS = "lbs_plus"      # Location-based services (traveler demographics)
    CVD_PLUS = "cvd_plus"      # Connected vehicle data (vehicle attributes)
    AGPS = "agps"              # Aggregated GPS


class DayType(str, Enum):
    ALL = "all"
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class Direction(str, Enum):
    BIDIRECTIONAL = "bidirectional"
    WITH = "with"
    AGAINST = "against"


# Base URL for Streetlight SATC API
STREETLIGHT_BASE_URL = "https://api.streetlightdata.com/satc/v1"


# =============================================================================
# Response Models
# =============================================================================

class IncomeBreakdown(BaseModel):
    """Traveler income distribution (from lbs_plus source)."""
    under_15k: Optional[float] = None
    income_15k_25k: Optional[float] = None
    income_25k_35k: Optional[float] = None
    income_35k_50k: Optional[float] = None
    income_50k_75k: Optional[float] = None
    income_75k_100k: Optional[float] = None
    income_100k_150k: Optional[float] = None
    income_150k_200k: Optional[float] = None
    over_200k: Optional[float] = None


class TripPurposeBreakdown(BaseModel):
    """Trip purpose distribution (from lbs_plus source)."""
    hbw: Optional[float] = None    # Home-Based Work
    hbo: Optional[float] = None    # Home-Based Other
    nhbw: Optional[float] = None   # Non-Home-Based Work
    wbo: Optional[float] = None    # Work-Based Other


class VehicleClassBreakdown(BaseModel):
    """Vehicle body class distribution (from cvd_plus source)."""
    sedan: Optional[float] = None
    suv: Optional[float] = None
    truck: Optional[float] = None
    pickup: Optional[float] = None
    minivan: Optional[float] = None
    hatchback: Optional[float] = None
    coupe: Optional[float] = None
    cuv: Optional[float] = None
    other: Optional[float] = None


class PowerTrainBreakdown(BaseModel):
    """Vehicle power train distribution (from cvd_plus source)."""
    ev: Optional[float] = None           # Electric Vehicle
    hybrid: Optional[float] = None       # Hybrid
    ice: Optional[float] = None          # Internal Combustion Engine
    other: Optional[float] = None


class SegmentMetrics(BaseModel):
    """Traffic metrics for a single road segment."""
    segment_id: str

    # Volume metrics
    trips_volume: Optional[int] = None       # Estimated daily traffic volume
    trips_sample_count: Optional[int] = None # Sample size
    vmt: Optional[float] = None              # Vehicle Miles Traveled

    # Speed metrics
    avg_speed: Optional[float] = None        # Average speed (mph)
    free_flow_speed: Optional[float] = None  # 95th percentile speed (mph)
    max_1hr_speed: Optional[float] = None    # Peak hourly average speed

    # Geometry (GeoJSON LineString)
    geometry: Optional[dict] = None

    # Temporal context
    year_month: Optional[str] = None
    day_type: Optional[str] = None
    day_part: Optional[str] = None


class TrafficAnalysis(BaseModel):
    """Aggregated traffic analysis for a location."""
    latitude: float
    longitude: float
    radius_miles: float

    # Aggregated volume metrics
    total_segments: int = 0
    total_daily_traffic: Optional[int] = None    # Sum of all segment volumes
    avg_segment_volume: Optional[int] = None     # Average per segment
    total_vmt: Optional[float] = None            # Total VMT in area

    # Aggregated speed metrics
    avg_speed: Optional[float] = None
    avg_free_flow_speed: Optional[float] = None

    # Traveler demographics (aggregated from lbs_plus)
    income_breakdown: Optional[IncomeBreakdown] = None
    trip_purpose_breakdown: Optional[TripPurposeBreakdown] = None

    # Vehicle attributes (aggregated from cvd_plus)
    vehicle_class_breakdown: Optional[VehicleClassBreakdown] = None
    power_train_breakdown: Optional[PowerTrainBreakdown] = None

    # Individual segment data (optional)
    segments: Optional[list[SegmentMetrics]] = None

    # Metadata
    data_source: str = "lbs_plus"
    date_range: Optional[str] = None
    segments_queried: int = 0  # For quota tracking


class DateAvailability(BaseModel):
    """Available date ranges for querying."""
    months: list[dict]  # [{"month": 1, "year": 2024}, ...]
    years: list[dict]   # [{"year": 2024}, ...]


class SegmentCountEstimate(BaseModel):
    """Estimate of segments in a geometry (for quota planning)."""
    segment_count: int
    geometry_type: str


# =============================================================================
# Streetlight API Client
# =============================================================================

class StreetlightClient:
    """Client for Streetlight Advanced Traffic Counts API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.STREETLIGHT_API_KEY
        if not self.api_key:
            raise ValueError(
                "Streetlight API key not configured. "
                "Set STREETLIGHT_API_KEY environment variable."
            )
        self.base_url = STREETLIGHT_BASE_URL
        self.headers = {"x-stl-key": self.api_key}

    async def check_date_ranges(
        self,
        country: str = "us",
        mode: TravelMode = TravelMode.VEHICLE,
        source: DataSource = DataSource.LBS_PLUS
    ) -> DateAvailability:
        """
        Check available date ranges for a given mode and source.

        This is a non-billable endpoint.
        """
        url = f"{self.base_url}/date_ranges/{country}/{mode.value}/{source.value}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()

        if data.get("status") == "error":
            raise ValueError(f"Streetlight API error: {data}")

        return DateAvailability(
            months=data.get("months", []),
            years=data.get("years", [])
        )

    async def get_geometry(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = 1.0,
        country: str = "us",
        mode: TravelMode = TravelMode.VEHICLE,
        source: DataSource = DataSource.LBS_PLUS
    ) -> dict:
        """
        Get road segment geometries within a radius of a point.

        This is a non-billable endpoint. Returns segment IDs and GeoJSON.
        """
        url = f"{self.base_url}/geometry"

        # Convert miles to meters for radius (max 5 miles / 8 km)
        radius_meters = min(radius_miles * 1609.34, 8000)

        payload = {
            "geometry": {
                "radius": {
                    "point": {
                        "type": "point",
                        "coordinates": [longitude, latitude]
                    },
                    "distance": radius_meters,
                    "distance_unit": "m"
                }
            },
            "mode": mode.value,
            "country": country,
            "source": source.value
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

        if data.get("status") == "error":
            raise ValueError(f"Streetlight geometry error: {data}")

        return data

    async def estimate_segment_count(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = 1.0,
        country: str = "us",
        mode: TravelMode = TravelMode.VEHICLE
    ) -> SegmentCountEstimate:
        """
        Estimate number of segments in a geometry (for quota planning).

        This is a non-billable endpoint. Use before making metrics calls
        to understand quota impact.
        """
        # Get geometry to count segments
        geometry_data = await self.get_geometry(
            latitude, longitude, radius_miles, country, mode
        )

        segment_count = geometry_data.get("query_rows", 0)

        return SegmentCountEstimate(
            segment_count=segment_count,
            geometry_type="radius"
        )

    async def get_metrics(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = 1.0,
        country: str = "us",
        mode: TravelMode = TravelMode.VEHICLE,
        source: DataSource = DataSource.LBS_PLUS,
        day_type: DayType = DayType.ALL,
        day_part: str = "all",
        direction: Direction = Direction.BIDIRECTIONAL,
        year: Optional[int] = None,
        month: Optional[int] = None,
        fields: Optional[list[str]] = None
    ) -> dict:
        """
        Get traffic metrics for segments within a radius.

        This is a BILLABLE endpoint. Charges based on:
        - Number of segments in geometry
        - Number of date periods requested

        Requesting multiple fields in a single call does NOT increase quota.
        """
        url = f"{self.base_url}/metrics"

        # Convert miles to meters for radius
        radius_meters = min(radius_miles * 1609.34, 8000)

        # Default fields for site selection analysis
        if fields is None:
            fields = [
                "segment_id",
                "trips_volume",
                "vmt",
                "avg_speed",
            ]

            # Add demographic fields for lbs_plus source
            if source == DataSource.LBS_PLUS:
                fields.extend(["income", "trip_purpose"])

            # Add vehicle attribute fields for cvd_plus source
            elif source == DataSource.CVD_PLUS:
                fields.extend(["body_class", "power_train"])

        payload = {
            "geometry": {
                "radius": {
                    "point": {
                        "type": "point",
                        "coordinates": [longitude, latitude]
                    },
                    "distance": radius_meters,
                    "distance_unit": "m"
                }
            },
            "fields": fields,
            "country": country,
            "mode": mode.value,
            "day_type": day_type.value,
            "day_part": day_part,
            "direction": direction.value,
            "source": source.value
        }

        # Add date filtering
        if year:
            if month:
                payload["date"] = {"year": year, "month": month}
            else:
                payload["date"] = {"year": year}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()

        if data.get("status") == "error":
            raise ValueError(f"Streetlight metrics error: {data}")

        return data


# =============================================================================
# High-Level Analysis Functions
# =============================================================================

async def fetch_traffic_counts(
    latitude: float,
    longitude: float,
    radius_miles: float = 1.0,
    include_demographics: bool = True,
    include_vehicle_attributes: bool = False,
    year: Optional[int] = None,
    month: Optional[int] = None
) -> TrafficAnalysis:
    """
    Fetch comprehensive traffic analysis for a location.

    This is the main entry point for traffic count analysis.
    Combines data from lbs_plus (demographics) and optionally cvd_plus (vehicles).

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        radius_miles: Analysis radius (0.5-5 miles)
        include_demographics: Include traveler income/trip purpose (lbs_plus)
        include_vehicle_attributes: Include vehicle class/powertrain (cvd_plus)
        year: Optional year filter (defaults to most recent)
        month: Optional month filter

    Returns:
        TrafficAnalysis with aggregated metrics
    """
    client = StreetlightClient()

    # Validate radius (Streetlight max is 5 miles / 8 km)
    radius_miles = min(max(radius_miles, 0.25), 5.0)

    # Fetch base traffic metrics with demographics (lbs_plus)
    metrics_data = await client.get_metrics(
        latitude=latitude,
        longitude=longitude,
        radius_miles=radius_miles,
        source=DataSource.LBS_PLUS if include_demographics else DataSource.AGPS,
        year=year,
        month=month
    )

    # Parse segment data
    segments = []
    columns = metrics_data.get("columns", [])
    data_rows = metrics_data.get("data", [])

    for row in data_rows:
        row_dict = dict(zip(columns, row))
        segment = SegmentMetrics(
            segment_id=str(row_dict.get("segment_id", "")),
            trips_volume=safe_int(row_dict.get("trips_volume")),
            vmt=safe_float(row_dict.get("vmt")),
            avg_speed=safe_float(row_dict.get("avg_speed")),
            year_month=row_dict.get("year_month"),
            day_type=row_dict.get("day_type"),
            day_part=row_dict.get("day_part")
        )
        segments.append(segment)

    # Aggregate metrics
    total_volume = sum(s.trips_volume or 0 for s in segments)
    total_vmt = sum(s.vmt or 0.0 for s in segments)
    speeds = [s.avg_speed for s in segments if s.avg_speed]
    avg_speed = sum(speeds) / len(speeds) if speeds else None

    # Parse income breakdown if available
    income_breakdown = None
    if include_demographics and "income" in columns:
        income_breakdown = _aggregate_income_data(data_rows, columns)

    # Parse trip purpose if available
    trip_purpose = None
    if include_demographics and "trip_purpose" in columns:
        trip_purpose = _aggregate_trip_purpose_data(data_rows, columns)

    # Fetch vehicle attributes separately if requested (requires cvd_plus)
    vehicle_class = None
    power_train = None
    if include_vehicle_attributes:
        try:
            cvd_data = await client.get_metrics(
                latitude=latitude,
                longitude=longitude,
                radius_miles=radius_miles,
                source=DataSource.CVD_PLUS,
                year=year,
                month=month,
                fields=["segment_id", "body_class", "power_train"]
            )
            vehicle_class = _aggregate_vehicle_class_data(
                cvd_data.get("data", []),
                cvd_data.get("columns", [])
            )
            power_train = _aggregate_power_train_data(
                cvd_data.get("data", []),
                cvd_data.get("columns", [])
            )
        except Exception as e:
            # Vehicle attributes are supplemental - don't fail if unavailable
            print(f"CVD+ data fetch failed (non-fatal): {e}")

    return TrafficAnalysis(
        latitude=latitude,
        longitude=longitude,
        radius_miles=radius_miles,
        total_segments=len(segments),
        total_daily_traffic=total_volume if total_volume > 0 else None,
        avg_segment_volume=total_volume // len(segments) if segments else None,
        total_vmt=round(total_vmt, 2) if total_vmt > 0 else None,
        avg_speed=round(avg_speed, 1) if avg_speed else None,
        income_breakdown=income_breakdown,
        trip_purpose_breakdown=trip_purpose,
        vehicle_class_breakdown=vehicle_class,
        power_train_breakdown=power_train,
        segments=segments,
        segments_queried=len(segments),
        date_range=f"{year}-{month:02d}" if year and month else str(year) if year else None
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _aggregate_income_data(data_rows: list, columns: list) -> IncomeBreakdown:
    """Aggregate income distribution across all segments."""
    income_idx = columns.index("income") if "income" in columns else None
    if income_idx is None:
        return IncomeBreakdown()

    # Streetlight returns income as a distribution object
    # Aggregate percentages across all segments
    totals = {}
    count = 0

    for row in data_rows:
        income_data = row[income_idx]
        if isinstance(income_data, dict):
            for bracket, pct in income_data.items():
                totals[bracket] = totals.get(bracket, 0) + (pct or 0)
            count += 1

    if count == 0:
        return IncomeBreakdown()

    # Average across segments and map to our model
    return IncomeBreakdown(
        under_15k=safe_float(totals.get("<$15,000", 0) / count),
        income_15k_25k=safe_float(totals.get("$15,000-$24,999", 0) / count),
        income_25k_35k=safe_float(totals.get("$25,000-$34,999", 0) / count),
        income_35k_50k=safe_float(totals.get("$35,000-$49,999", 0) / count),
        income_50k_75k=safe_float(totals.get("$50,000-$74,999", 0) / count),
        income_75k_100k=safe_float(totals.get("$75,000-$99,999", 0) / count),
        income_100k_150k=safe_float(totals.get("$100,000-$149,999", 0) / count),
        income_150k_200k=safe_float(totals.get("$150,000-$199,999", 0) / count),
        over_200k=safe_float(totals.get("$200,000+", 0) / count),
    )


def _aggregate_trip_purpose_data(data_rows: list, columns: list) -> TripPurposeBreakdown:
    """Aggregate trip purpose distribution across all segments."""
    purpose_idx = columns.index("trip_purpose") if "trip_purpose" in columns else None
    if purpose_idx is None:
        return TripPurposeBreakdown()

    totals = {"HBW": 0, "HBO": 0, "NHBW": 0, "WBO": 0}
    count = 0

    for row in data_rows:
        purpose_data = row[purpose_idx]
        if isinstance(purpose_data, dict):
            for purpose, pct in purpose_data.items():
                if purpose in totals:
                    totals[purpose] += (pct or 0)
            count += 1

    if count == 0:
        return TripPurposeBreakdown()

    return TripPurposeBreakdown(
        hbw=safe_float(totals["HBW"] / count),
        hbo=safe_float(totals["HBO"] / count),
        nhbw=safe_float(totals["NHBW"] / count),
        wbo=safe_float(totals["WBO"] / count),
    )


def _aggregate_vehicle_class_data(data_rows: list, columns: list) -> VehicleClassBreakdown:
    """Aggregate vehicle class distribution across all segments."""
    class_idx = columns.index("body_class") if "body_class" in columns else None
    if class_idx is None:
        return VehicleClassBreakdown()

    totals = {}
    count = 0

    for row in data_rows:
        class_data = row[class_idx]
        if isinstance(class_data, dict):
            for vehicle_type, pct in class_data.items():
                totals[vehicle_type] = totals.get(vehicle_type, 0) + (pct or 0)
            count += 1

    if count == 0:
        return VehicleClassBreakdown()

    return VehicleClassBreakdown(
        sedan=safe_float(totals.get("sedan", 0) / count),
        suv=safe_float(totals.get("suv", 0) / count),
        truck=safe_float(totals.get("truck", 0) / count),
        pickup=safe_float(totals.get("pickup", 0) / count),
        minivan=safe_float(totals.get("minivan", 0) / count),
        hatchback=safe_float(totals.get("hatchback", 0) / count),
        coupe=safe_float(totals.get("coupe", 0) / count),
        cuv=safe_float(totals.get("cuv", 0) / count),
        other=safe_float(totals.get("other", 0) / count),
    )


def _aggregate_power_train_data(data_rows: list, columns: list) -> PowerTrainBreakdown:
    """Aggregate power train distribution across all segments."""
    train_idx = columns.index("power_train") if "power_train" in columns else None
    if train_idx is None:
        return PowerTrainBreakdown()

    totals = {"ev": 0, "hybrid": 0, "ice": 0, "other": 0}
    count = 0

    for row in data_rows:
        train_data = row[train_idx]
        if isinstance(train_data, dict):
            for train_type, pct in train_data.items():
                key = train_type.lower().replace(" ", "_")
                if key in totals:
                    totals[key] += (pct or 0)
                elif "internal" in key.lower():
                    totals["ice"] += (pct or 0)
            count += 1

    if count == 0:
        return PowerTrainBreakdown()

    return PowerTrainBreakdown(
        ev=safe_float(totals["ev"] / count),
        hybrid=safe_float(totals["hybrid"] / count),
        ice=safe_float(totals["ice"] / count),
        other=safe_float(totals["other"] / count),
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
