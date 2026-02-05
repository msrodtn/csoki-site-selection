"""
Mapbox Matrix API Service

Calculates travel times and distances between multiple origin/destination points.
Supports batch processing for large datasets (25x25 limit per request).

Key features:
- Drive-time coverage analysis for site selection
- Competition accessibility scoring
- Market gap identification
- Caching to reduce API costs

API Docs: https://docs.mapbox.com/api/navigation/matrix/

Pricing:
- $0.10 per 100 elements (standard)
- 25x25 matrix = 625 elements = ~$0.63 per request
"""

import httpx
import hashlib
import json
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from enum import Enum

from app.core.config import settings


class TravelProfile(str, Enum):
    """Supported travel profiles for Matrix API."""
    DRIVING = "driving"
    DRIVING_TRAFFIC = "driving-traffic"  # Real-time traffic
    WALKING = "walking"
    CYCLING = "cycling"


class MatrixRequest(BaseModel):
    """Request model for Matrix API calculations."""
    origins: List[Tuple[float, float]] = Field(
        ...,
        description="List of origin coordinates as (longitude, latitude) tuples",
        max_length=25,
    )
    destinations: List[Tuple[float, float]] = Field(
        ...,
        description="List of destination coordinates as (longitude, latitude) tuples",
        max_length=25,
    )
    profile: TravelProfile = Field(
        default=TravelProfile.DRIVING,
        description="Travel profile for routing calculations",
    )

    class Config:
        use_enum_values = True


class MatrixElement(BaseModel):
    """Single element in the matrix result (origin → destination pair)."""
    origin_index: int
    destination_index: int
    duration_seconds: Optional[float] = None  # Travel time in seconds
    distance_meters: Optional[float] = None   # Distance in meters

    @property
    def duration_minutes(self) -> Optional[float]:
        """Get duration in minutes."""
        return self.duration_seconds / 60 if self.duration_seconds else None

    @property
    def distance_miles(self) -> Optional[float]:
        """Get distance in miles."""
        return self.distance_meters / 1609.34 if self.distance_meters else None


class MatrixResponse(BaseModel):
    """Response model for Matrix API calculations."""
    elements: List[MatrixElement]
    profile: str
    total_origins: int
    total_destinations: int
    cached: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CompetitorAccessResult(BaseModel):
    """Result for competitor accessibility analysis."""
    site_latitude: float
    site_longitude: float
    competitors: List[dict]  # Competitor store details with travel times
    profile: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)


# Simple in-memory cache (consider Redis for production)
_matrix_cache: dict = {}
CACHE_TTL_HOURS = 24


def _get_cache_key(
    origins: List[Tuple[float, float]],
    destinations: List[Tuple[float, float]],
    profile: str,
) -> str:
    """Generate a cache key for the matrix request."""
    data = {
        "origins": origins,
        "destinations": destinations,
        "profile": profile,
    }
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _is_cache_valid(cache_entry: dict) -> bool:
    """Check if a cache entry is still valid."""
    if "timestamp" not in cache_entry:
        return False
    cache_time = datetime.fromisoformat(cache_entry["timestamp"])
    return datetime.utcnow() - cache_time < timedelta(hours=CACHE_TTL_HOURS)


async def calculate_matrix(
    origins: List[Tuple[float, float]],
    destinations: List[Tuple[float, float]],
    profile: TravelProfile = TravelProfile.DRIVING,
    use_cache: bool = True,
) -> MatrixResponse:
    """
    Calculate travel times and distances between origins and destinations.

    Args:
        origins: List of (longitude, latitude) tuples (max 25)
        destinations: List of (longitude, latitude) tuples (max 25)
        profile: Travel profile (driving, driving-traffic, walking, cycling)
        use_cache: Whether to use cached results if available

    Returns:
        MatrixResponse with travel times and distances for each pair

    Raises:
        ValueError: If origins or destinations exceed 25 points
        httpx.HTTPStatusError: If API request fails
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    if len(origins) > 25:
        raise ValueError(f"Maximum 25 origins allowed, got {len(origins)}")
    if len(destinations) > 25:
        raise ValueError(f"Maximum 25 destinations allowed, got {len(destinations)}")

    profile_str = profile.value if isinstance(profile, TravelProfile) else profile

    # Check cache
    cache_key = _get_cache_key(origins, destinations, profile_str)
    if use_cache and cache_key in _matrix_cache:
        cache_entry = _matrix_cache[cache_key]
        if _is_cache_valid(cache_entry):
            return MatrixResponse(
                elements=[MatrixElement(**e) for e in cache_entry["elements"]],
                profile=profile_str,
                total_origins=len(origins),
                total_destinations=len(destinations),
                cached=True,
                timestamp=datetime.fromisoformat(cache_entry["timestamp"]),
            )

    # Build coordinates string
    # Format: "lng,lat;lng,lat;..."
    all_coords = origins + destinations
    coords_str = ";".join([f"{lng},{lat}" for lng, lat in all_coords])

    # Build sources and destinations indices
    # Sources are 0 to len(origins)-1, destinations are len(origins) to end
    sources_str = ";".join([str(i) for i in range(len(origins))])
    destinations_str = ";".join([str(i) for i in range(len(origins), len(all_coords))])

    # Build API URL
    base_url = f"https://api.mapbox.com/directions-matrix/v1/mapbox/{profile_str}"
    url = f"{base_url}/{coords_str}"

    params = {
        "access_token": settings.MAPBOX_ACCESS_TOKEN,
        "sources": sources_str,
        "destinations": destinations_str,
        "annotations": "duration,distance",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

    # Parse response
    elements = []
    durations = data.get("durations", [])
    distances = data.get("distances", [])

    for origin_idx, (dur_row, dist_row) in enumerate(zip(durations, distances)):
        for dest_idx, (duration, distance) in enumerate(zip(dur_row, dist_row)):
            elements.append(MatrixElement(
                origin_index=origin_idx,
                destination_index=dest_idx,
                duration_seconds=duration,
                distance_meters=distance,
            ))

    # Cache the result
    timestamp = datetime.utcnow()
    _matrix_cache[cache_key] = {
        "elements": [e.model_dump() for e in elements],
        "timestamp": timestamp.isoformat(),
    }

    return MatrixResponse(
        elements=elements,
        profile=profile_str,
        total_origins=len(origins),
        total_destinations=len(destinations),
        cached=False,
        timestamp=timestamp,
    )


async def calculate_matrix_batched(
    origins: List[Tuple[float, float]],
    destinations: List[Tuple[float, float]],
    profile: TravelProfile = TravelProfile.DRIVING,
    batch_size: int = 25,
) -> MatrixResponse:
    """
    Calculate matrix for large datasets by batching requests.

    Automatically splits requests that exceed the 25x25 limit.

    Args:
        origins: List of (longitude, latitude) tuples (no limit)
        destinations: List of (longitude, latitude) tuples (no limit)
        profile: Travel profile
        batch_size: Maximum points per batch (default 25, Mapbox limit)

    Returns:
        Combined MatrixResponse with all results
    """
    all_elements = []

    # Batch origins and destinations
    for orig_start in range(0, len(origins), batch_size):
        orig_batch = origins[orig_start:orig_start + batch_size]

        for dest_start in range(0, len(destinations), batch_size):
            dest_batch = destinations[dest_start:dest_start + batch_size]

            # Calculate this batch
            batch_result = await calculate_matrix(
                origins=orig_batch,
                destinations=dest_batch,
                profile=profile,
            )

            # Adjust indices for the full matrix
            for element in batch_result.elements:
                adjusted_element = MatrixElement(
                    origin_index=orig_start + element.origin_index,
                    destination_index=dest_start + element.destination_index,
                    duration_seconds=element.duration_seconds,
                    distance_meters=element.distance_meters,
                )
                all_elements.append(adjusted_element)

    return MatrixResponse(
        elements=all_elements,
        profile=profile.value if isinstance(profile, TravelProfile) else profile,
        total_origins=len(origins),
        total_destinations=len(destinations),
        cached=False,
    )


async def analyze_competitor_access(
    site_location: Tuple[float, float],
    competitor_locations: List[dict],
    profile: TravelProfile = TravelProfile.DRIVING_TRAFFIC,
    max_competitors: int = 25,
) -> CompetitorAccessResult:
    """
    Analyze travel times from a potential site to nearby competitors.

    Args:
        site_location: (longitude, latitude) of the potential site
        competitor_locations: List of competitor dicts with 'id', 'longitude', 'latitude', 'brand', etc.
        profile: Travel profile (driving-traffic recommended for realistic times)
        max_competitors: Maximum competitors to analyze (default 25, API limit)

    Returns:
        CompetitorAccessResult with competitors sorted by travel time
    """
    # Limit competitors to API maximum
    competitors = competitor_locations[:max_competitors]

    if not competitors:
        return CompetitorAccessResult(
            site_latitude=site_location[1],
            site_longitude=site_location[0],
            competitors=[],
            profile=profile.value if isinstance(profile, TravelProfile) else profile,
        )

    # Build destination coordinates
    destinations = [(c["longitude"], c["latitude"]) for c in competitors]

    # Calculate matrix (single origin to multiple destinations)
    result = await calculate_matrix(
        origins=[site_location],
        destinations=destinations,
        profile=profile,
    )

    # Combine results with competitor data
    competitors_with_times = []
    for element in result.elements:
        competitor = competitors[element.destination_index].copy()
        competitor["travel_time_seconds"] = element.duration_seconds
        competitor["travel_time_minutes"] = element.duration_minutes
        competitor["distance_meters"] = element.distance_meters
        competitor["distance_miles"] = element.distance_miles
        competitors_with_times.append(competitor)

    # Sort by travel time
    competitors_with_times.sort(
        key=lambda c: c.get("travel_time_seconds") or float("inf")
    )

    return CompetitorAccessResult(
        site_latitude=site_location[1],
        site_longitude=site_location[0],
        competitors=competitors_with_times,
        profile=profile.value if isinstance(profile, TravelProfile) else profile,
    )


def clear_matrix_cache():
    """Clear the in-memory matrix cache."""
    global _matrix_cache
    _matrix_cache = {}


def get_cache_stats() -> dict:
    """Get cache statistics."""
    valid_entries = sum(1 for entry in _matrix_cache.values() if _is_cache_valid(entry))
    return {
        "total_entries": len(_matrix_cache),
        "valid_entries": valid_entries,
        "expired_entries": len(_matrix_cache) - valid_entries,
    }
