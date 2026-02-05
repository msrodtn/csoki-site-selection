"""
Mapbox Isochrone API Service

Fetches drive-time polygons showing areas reachable within a given time.
Used for coverage analysis and service area visualization.

API Docs: https://docs.mapbox.com/api/navigation/isochrone/
"""

import httpx
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

from app.core.config import settings


class IsochroneProfile(str, Enum):
    """Travel profiles for isochrone calculations."""
    DRIVING = "driving"
    DRIVING_TRAFFIC = "driving-traffic"
    WALKING = "walking"
    CYCLING = "cycling"


class IsochroneRequest(BaseModel):
    """Request model for isochrone API."""
    latitude: float
    longitude: float
    minutes: int = Field(default=10, ge=1, le=60)
    profile: IsochroneProfile = IsochroneProfile.DRIVING
    contours_colors: Optional[List[str]] = None  # Hex colors for each contour
    polygons: bool = True  # Return polygons vs linestrings
    denoise: float = Field(default=1.0, ge=0, le=1)  # Simplification factor


class IsochroneResponse(BaseModel):
    """Response model for isochrone API."""
    type: str = "FeatureCollection"
    features: List[Dict[str, Any]]
    latitude: float
    longitude: float
    minutes: int
    profile: str


# Base URL for Isochrone API
ISOCHRONE_API_BASE = "https://api.mapbox.com/isochrone/v1/mapbox"


async def fetch_isochrone(
    latitude: float,
    longitude: float,
    minutes: int = 10,
    profile: IsochroneProfile = IsochroneProfile.DRIVING,
    contours_colors: Optional[List[str]] = None,
    polygons: bool = True,
    denoise: float = 1.0,
) -> IsochroneResponse:
    """
    Fetch an isochrone polygon from Mapbox API.

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        minutes: Travel time in minutes (1-60)
        profile: Travel profile (driving, driving-traffic, walking, cycling)
        contours_colors: Optional hex colors for contours
        polygons: Return polygons (True) or linestrings (False)
        denoise: Simplification factor (0-1, higher = more simplified)

    Returns:
        IsochroneResponse with GeoJSON FeatureCollection
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    profile_str = profile.value if isinstance(profile, IsochroneProfile) else profile
    url = f"{ISOCHRONE_API_BASE}/{profile_str}/{longitude},{latitude}"

    params = {
        "access_token": settings.MAPBOX_ACCESS_TOKEN,
        "contours_minutes": minutes,
        "polygons": str(polygons).lower(),
        "denoise": denoise,
    }

    if contours_colors:
        params["contours_colors"] = ",".join(contours_colors)

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

    return IsochroneResponse(
        type=data.get("type", "FeatureCollection"),
        features=data.get("features", []),
        latitude=latitude,
        longitude=longitude,
        minutes=minutes,
        profile=profile_str,
    )


async def fetch_multi_contour_isochrone(
    latitude: float,
    longitude: float,
    minutes_list: List[int],
    profile: IsochroneProfile = IsochroneProfile.DRIVING,
    colors: Optional[List[str]] = None,
) -> IsochroneResponse:
    """
    Fetch multiple isochrone contours in a single request.

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        minutes_list: List of travel times in minutes (max 4)
        profile: Travel profile
        colors: Optional hex colors for each contour

    Returns:
        IsochroneResponse with multiple polygon features
    """
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    if len(minutes_list) > 4:
        raise ValueError("Maximum 4 contours allowed per request")

    profile_str = profile.value if isinstance(profile, IsochroneProfile) else profile
    url = f"{ISOCHRONE_API_BASE}/{profile_str}/{longitude},{latitude}"

    # Join minutes with commas
    contours_minutes = ",".join(str(m) for m in sorted(minutes_list))

    params = {
        "access_token": settings.MAPBOX_ACCESS_TOKEN,
        "contours_minutes": contours_minutes,
        "polygons": "true",
    }

    if colors:
        params["contours_colors"] = ",".join(colors[:len(minutes_list)])

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

    return IsochroneResponse(
        type=data.get("type", "FeatureCollection"),
        features=data.get("features", []),
        latitude=latitude,
        longitude=longitude,
        minutes=max(minutes_list),
        profile=profile_str,
    )


# Default colors for multi-contour isochrones (green to red)
DEFAULT_ISOCHRONE_COLORS = [
    "22C55E",  # Green - closest
    "EAB308",  # Yellow
    "F97316",  # Orange
    "EF4444",  # Red - farthest
]
